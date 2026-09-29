"""Known-route collection with explicit truth feedback; stereo-only SLAM evaluation."""
import gc,json,math,signal,time
import numpy as np
import rclpy
from rclpy.signals import SignalHandlerOptions
from sensor_msgs.msg import PointCloud2
from std_msgs.msg import String
from rtabmap_msgs.msg import Info,MapGraph
from nav_msgs.msg import Path as PathMsg
from uw_benchmark.m2_case import Case as SensorCase
from uw_benchmark.porth_case import Case as SlamCase
from uw_benchmark.m2_metrics import evaluate,render
from uw_runtime.artifacts import write_json
from uw_controller.core import rpy
from uw_navigation.survey import Follower


class Case(SensorCase):
    # Share the exact observation and native-cloud export implementation used
    # by the accepted local Porth run, without its task/navigation controller.
    slam_info=SlamCase.slam_info
    slam_graph=SlamCase.slam_graph
    slam_cloud=SlamCase.slam_cloud
    export_cloud=SlamCase.export_cloud
    def __init__(self):
        super().__init__()
        self.stream.close();(self.out/'m2-samples.jsonl').rename(self.out/'m3-samples.jsonl')
        self.stream=(self.out/'m3-samples.jsonl').open('a',buffering=1)
        self.plan=json.loads((self.out/'survey-plan.json').read_text());self.follower=Follower(self.plan['route_enu'],self.plan['maximum_speed_m_s'],self.plan.get('route_yaw_enu'))
        self.slam_rows=[];self.graph_nodes=0;self.graph_links=0;self.cloud=None;self.cloud_updates=0;self.last_slam_wall=0
        self.max_cloud_points=0;self.graph_poses=[];self.initial_disarmed=False;self.initial_terminal_disarmed=False
        self.orb=self.cfg.get('slam_profile')=='orbslam3_stereo';self.orb_status={};self.orb_good_wall=0.;self.orb_lost_since=None;self.orb_initial_map=None
        if self.orb:
            self.create_subscription(String,'slam/status',self.on_orb_status,10)
            self.create_subscription(PathMsg,'slam/trajectory',self.on_orb_path,1)
        else:
            self.slam_path=self.create_publisher(PathMsg,'slam/trajectory',1)
            self.create_subscription(Info,'slam/info',self.slam_info,10)
            self.create_subscription(MapGraph,'slam/map_graph',self.slam_graph,5)
        self.create_subscription(PointCloud2,'slam/cloud_map',self.slam_cloud,1)
        self.stopping=None;self.completed=False;self.progress={};self.next_status=0;self.next_control=0;self.tracking=[]
        self.last_sample={};self.last_safety=None;self.last_capture=0
        self.progress_anchor=0.;self.progress_wall=None
        self.collection_started=None
        # The retained evidence rows are acyclic. Automatic cyclic collection
        # traverses the entire growing history and can block this safety-critical
        # command source. Refcount reclamation remains active; bounded process
        # teardown reclaims the history. All dense history is also in MCAP.
        gc.disable()
        self.maximum_spin_sec=0.
        self.event('survey_configuration',control_state_source='PRIVILEGED_DEBUG',slam_truth_input=False,
            plan_sha256=self.cfg['survey_plan_sha256'],explicit_arm=self.cfg['execute_path'])
    def on_orb_status(self,m):
        value=json.loads(m.data);now=time.monotonic()
        # Only a newly processed source stamp refreshes the processing lease.
        if value['stamp']<=self.orb_status.get('stamp',-1):return
        self.orb_status=value;self.last_slam_wall=now
        self.slam_rows.append(dict(wall=now,loop_closure_id=0,proximity_id=0,**value))
        if value['tracked']:self.orb_good_wall=now;self.orb_lost_since=None
        elif self.orb_lost_since is None:self.orb_lost_since=now
        with (self.out/'slam-events.jsonl').open('a') as f:f.write(json.dumps(dict(wall=now,**value))+'\n')
    def on_orb_path(self,m):
        self.graph_nodes=len(m.poses);self.graph_poses=[[p.pose.position.x,p.pose.position.y,p.pose.position.z] for p in m.poses]
    def sample(self,kind,**p):
        # Keep high-frequency messages in MCAP; JSON diagnostics at <=10 Hz.
        now=time.monotonic()
        if hasattr(self,'last_sample'):
            if now-self.last_sample.get(kind,0)<.1:return
            self.last_sample[kind]=now
        super().sample(kind,**p)
    def image(self,m,side):
        super().image(m,side)
        if side==0 and time.monotonic()-getattr(self,'last_capture',0)>30:
            import cv2
            self.last_capture=time.monotonic();frame=np.frombuffer(m.data,dtype=np.uint8).reshape(m.height,m.width,3)
            cv2.imwrite(str(self.out/f'figures/survey-left-{self.sequence:07d}.png'),cv2.cvtColor(frame,cv2.COLOR_RGB2BGR))
    def stop(self,reason=None):
        if self.stopping is not None:return
        if reason:self.errors.append(reason)
        self.stopping=time.monotonic();self.event('survey_stopping',reason=reason or 'collection_complete')
        self.call('FAULT' if reason and self.armed else 'DISARM')
    def tick(self):
        if self.done:return
        now=time.monotonic()
        if self.future and self.future.done():
            r=self.future.result();action=self.action;self.future=None
            self.event('service_response',action=action,accepted=r.accepted,state=r.state,reason=r.reason)
            if action=='ARM' and r.accepted:
                self.armed=True;self.token=r.token;self.generation=r.generation;self.begin=now
            elif action=='ARM':self.stop('ARM rejected: '+r.reason)
            elif action in ('DISARM','FAULT'):self.armed=False;self.disarmed=r.state=='DISARMED'
        if self.stopping is not None:
            if now-self.stopping>2:self.finish()
            return
        if self.begin is None:
            if now-self.started>self.cfg['startup_timeout_sec']:self.stop('startup timeout');return
            # In this explicitly truth-controlled capture only, a zero-velocity
            # closed loop can stabilize the buoyant body for sensor-only VIO
            # initialization. It is an explicit ARM, never a launch side effect.
            ready=(len(self.truth)>50 and self.guard.get('ready') and
                all(now-self.sensors.get('image_'+side,{}).get('wall',0)<.20 for side in ('left','right')))
            if ready:
                self.initial_disarmed=self.guard.get('state')=='DISARMED';self.initial_terminal_disarmed=self.terminal.get('state')=='DISARMED'
                if self.cfg['execute_path']:
                    if not self.future:self.event('ready',startup_disarmed=self.initial_disarmed and self.initial_terminal_disarmed);self.call('ARM')
                else:self.begin=now
            return
        if self.elapsed()>self.cfg['duration_sec']:
            self.stop('finite duration reached before prescribed collection completed' if self.cfg['execute_path'] else None);return
        if self.armed:
            if self.elapsed()>.3 and self.guard.get('state')!='ARMED':self.stop('Guard '+str(self.guard));return
            if not self.truth or now-self.truth[-1]['wall']>.20:self.stop('truth feedback stale');return
            if self.collection_started is None:
                if self.elapsed()>20:self.stop('Stationary SLAM initialization timeout');return
                if any(now-self.sensors.get('image_'+side,{}).get('wall',0)>.5 for side in ('left','right')):self.stop('initialization camera stale');return
                if now>=self.next_control:self.next_control=now+.045;self.command([0.,0.,0.,0.])
                if self.elapsed()>3 and (self.orb_status.get('tracked',False) if self.orb else self.last_health.get('state') in ('READY_STATIC','TRACKING')) and len(self.slam_rows)>1:
                    self.collection_started=now;self.orb_initial_map=self.orb_status.get('map_id') if self.orb else None;self.event('collection_started',initialization_hold_sec=self.elapsed(),state_source='PRIVILEGED_DEBUG')
                return
            if not self.orb and (now-self.last_health.get('wall',0)>.5 or self.last_health.get('state') not in ('READY_STATIC','TRACKING')):
                self.stop('SLAM collection estimator unhealthy: '+str(self.last_health));return
            if now-self.last_slam_wall>5:self.stop('SLAM processing stale');return
            if self.orb:
                if self.orb_status.get('fault') or self.orb_status.get('map_count',0)>1 or self.orb_status.get('map_id')!=self.orb_initial_map:self.stop('ORB fault or disconnected Atlas maps: '+str(self.orb_status));return
                if now-self.orb_good_wall>5:self.stop('ORB tracking lost for 5 seconds');return
                if not self.orb_status.get('tracked'):
                    if now>=self.next_control:self.next_control=now+.045;self.command([0.,0.,0.,0.])
                    return
            if any(now-self.sensors.get('image_'+side,{}).get('wall',0)>.5 for side in ('left','right')):self.stop('camera stale');return
            if now<self.next_control:return
            self.next_control=now+.045
            state=self.truth[-1];command,progress=self.follower.update(state['position'],state['quaternion']);self.progress=progress
            if self.progress_wall is None or progress['progress_m']>self.progress_anchor+.1:
                self.progress_wall=now;self.progress_anchor=progress['progress_m']
            if now-self.progress_wall>45:self.stop('Prescribed path made no progress for 45 s');return
            if progress['cross_track_m']>self.plan['tracking_abort_m']:
                self.stop('Prescribed corridor tracking error: '+str(progress['cross_track_m']));return
            if max(abs(x) for x in rpy(state['quaternion'])[:2])>math.radians(20):self.stop('attitude envelope');return
            self.command(command)
            if now>=self.next_status:
                self.next_status=now+1
                row=dict(wall=now,elapsed=self.elapsed(),clock_sec=(self.clock or 0)*1e-9,position=state['position'],command=command,
                    graph_nodes=self.graph_nodes,cloud_points=self.max_cloud_points,estimator=self.last_health.get('state'),guard=self.guard.get('state'),**progress)
                write_json(self.out/'survey-progress.json',row);self.tracking.append(row)
                with (self.out/'survey-tracking.jsonl').open('a') as stream:stream.write(json.dumps(row)+'\n')
            if progress['complete'] or progress['progress_m']>=self.cfg['survey_max_distance_m']:
                self.completed=True;self.stop()
    def finish(self):
        if self.done:return
        self.graph();self.stream.flush()
        metrics,data=evaluate(self.truth,self.estimates)
        points=self.export_cloud()
        graph=json.loads((self.out/'graph-inspection.json').read_text());truth_subs=graph['topics']['/'+self.prefix+'/sim/ground_truth/odometry']['subscribers']
        checks=dict(no_contract_errors=not self.errors,explicit_authority=self.initial_disarmed and self.initial_terminal_disarmed,
            collection_completed=self.completed if self.cfg['execute_path'] else True,
            stereo_slam_graph=self.graph_nodes>=3,stereo_map_points=points>=1000,
            slam_never_subscribed_truth=not any(x['name'] in ('rtabmap','openvins','orbslam3') for x in truth_subs),
            one_clock=len(graph['topics']['/clock']['publishers'])==1,
            native_neutral=bool(self.terminal) and all(abs(float(x))<1e-9 for x in self.terminal.get('receiver_setpoint',[1])),
            terminal_disarmed=self.terminal.get('state')=='DISARMED',
            map_tf=self.tf_edges.get(self.prefix+'/map->'+self.prefix+('/orb_body' if self.orb else '/odom'),0)>0)
        if self.orb:
            metrics={'auxiliary_openvins':metrics}
            tracked=[r for r in self.slam_rows if self.collection_started is not None and r['wall']>=self.collection_started]
            fraction=sum(r['tracked'] for r in tracked)/max(1,len(tracked))
            latency=float(np.percentile([r['latency_sec'] for r in tracked],99)) if tracked else None
            rate=(len(tracked)-1)/(tracked[-1]['stamp']-tracked[0]['stamp']) if len(tracked)>1 else 0.
            inputs=self.get_subscriber_names_and_types_by_node('orbslam3','/'+self.prefix)
            write_json(self.out/'orb-subscription-inspection.json',dict(subscriptions=inputs))
            names={name for name,_ in inputs}
            allowed={'/clock','/parameter_events',f'/{self.prefix}/sensors/stereo/left/image_raw',f'/{self.prefix}/sensors/stereo/right/image_raw'}
            checks.update(orb_sensor_only_inputs=bool(names) and names.issubset(allowed),orb_tracking_fraction=fraction>=self.spec['thresholds']['minimum_tracking_fraction_after_initialization'],orb_latency_p99=latency is not None and latency<=self.spec['thresholds']['maximum_online_latency_p99_sec'],orb_single_map=bool(tracked) and max(r['map_count'] for r in tracked)==1,orb_processing_rate=rate>=self.spec['thresholds']['minimum_processed_hz'])
            metrics.update(orb_processed_hz=rate,orb_tracking_fraction=fraction,orb_latency_p99_sec=latency,orb_loop_edges=self.orb_status.get('loop_edges',0),auxiliary_estimator='OPENVINS; not ORB input')
        passed=all(checks.values());self.event('case_complete',passed=passed)
        result=dict(status='PASS' if passed else 'FAIL',scope='KNOWN_ROUTE_SENSOR_COLLECTION',checks=checks,metrics=metrics,
            reason='collection checks passed' if passed else 'Failed: '+', '.join(k for k,v in checks.items() if not v),errors=self.errors,
            control_state_source='PRIVILEGED_DEBUG',slam_truth_input=False,full_cave_coverage='REQUIRES_OFFLINE_SURFACE_EVALUATION',
            route_length_m=self.plan['route_length_m'],requested_distance_m=self.cfg['survey_max_distance_m'],progress=self.progress,
            graph_nodes=self.graph_nodes,map_points=points,loop_closures=sum(x['loop_closure_id']>0 for x in self.slam_rows),
            proximity_detections=sum(x['proximity_id']>0 for x in self.slam_rows),maximum_executor_step_sec=self.maximum_spin_sec,sensor_counts={k:v['count'] for k,v in self.sensors.items()})
        if self.orb:result.update(slam_backend='ORB_SLAM3_STEREO',loop_closures='NOT_COUNTED; see accepted loop_edges',proximity_detections='NOT_APPLICABLE',map_product='SPARSE_LANDMARKS',full_cave_coverage='NOT_VERIFIED')
        write_json(self.out/'m3-metrics.json',result);write_json(self.out/'slam-metrics.json',result)
        render(self.out,self.truth,self.estimates,[])
        self.done=True;self.result=0 if passed else 1


def main(args=None):
    rclpy.init(args=args,signal_handler_options=SignalHandlerOptions.NO);node=Case();stop=[False]
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stop.__setitem__(0,True))
    try:
        while rclpy.ok() and not stop[0] and not node.done:
            before=time.monotonic();rclpy.spin_once(node,timeout_sec=.03)
            duration=time.monotonic()-before;node.maximum_spin_sec=max(node.maximum_spin_sec,duration)
            if duration>.08 and not node.done:node.event('slow_callback',duration_sec=duration)
    finally:
        result=node.result;node.stream.close();node.destroy_node();rclpy.try_shutdown()
    raise SystemExit(result)
