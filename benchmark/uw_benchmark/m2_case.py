"""Finite real-simulation M2 cases. Truth is read exclusively for evaluation/excitation."""
import copy,json,math,os,signal,time
from pathlib import Path
import cv2,numpy as np,yaml
import rclpy
from rclpy.node import Node
from rclpy.clock import Clock,ClockType
from rclpy.signals import SignalHandlerOptions
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image,Imu,CameraInfo
from nav_msgs.msg import Odometry
from std_msgs.msg import String
from rosgraph_msgs.msg import Clock as ClockMsg
from tf2_msgs.msg import TFMessage
from uw_interfaces.msg import ControlRequest
from uw_interfaces.srv import Control
from uw_perception.contracts import ExactPairs,intrinsics
from uw_robot.frames import rpy_quaternion
from uw_controller.core import rpy
from uw_benchmark.m2_metrics import rotation,evaluate,render
from uw_runtime.artifacts import write_json


def ns(s):return s.sec*1000000000+s.nanosec


class Case(Node):
    def __init__(self):
        super().__init__('m2_case')
        self.out=Path(self.declare_parameter('run_dir','').value);self.cfg=yaml.safe_load((self.out/'resolved_config.yaml').read_text())
        self.spec=yaml.safe_load((self.out/'acceptance.yaml').read_text());self.case=self.cfg['case_id'];self.prefix=self.cfg['namespace']
        self.started=time.monotonic();self.begin=None;self.clock=None;self.first_clock=None;self.last_clock_wall=0
        self.done=False;self.result=1;self.errors=[];self.truth=[];self.estimates=[];self.imu=[];self.health=[];self.sensors={};self.guard={};self.terminal={}
        self.last_perception={};self.last_health={};self.terminal_rows=[];self.events=[];self.stereo=[];self.pairs=ExactPairs();self.tf_edges={}
        self.future=None;self.action='';self.token='';self.generation=0;self.sequence=0;self.armed=False;self.disarmed=False;self.injected=None;self.restored=False
        self.stream=(self.out/'m2-samples.jsonl').open('w',buffering=1)
        self.client=self.create_client(Control,'control/authority');self.request_pub=self.create_publisher(ControlRequest,'control/request',1)
        self.fixture=self.create_publisher(String,'perception/fixture',1);self.native_fixture=self.create_publisher(String,'sim/terminal/fixture',1)
        self.create_subscription(ClockMsg,'/clock',self.on_clock,qos_profile_sensor_data)
        self.create_subscription(Odometry,'sim/ground_truth/odometry',lambda m:self.state(m,True),5)
        self.create_subscription(Odometry,'state/odometry',lambda m:self.state(m,False),5)
        self.create_subscription(Imu,'sensors/imu',self.on_imu,qos_profile_sensor_data)
        for side,name in enumerate(('left','right')):
            self.create_subscription(Image,f'sensors/stereo/{name}/image_raw',lambda m,s=side:self.image(m,s),qos_profile_sensor_data)
            self.create_subscription(CameraInfo,f'sensors/stereo/{name}/camera_info',lambda m,n=name:self.sensor('info_'+n,m),qos_profile_sensor_data)
        self.create_subscription(String,'perception/status',lambda m:setattr(self,'last_perception',json.loads(m.data)),1)
        self.create_subscription(String,'localization/status',self.on_health,5)
        self.create_subscription(String,'control/status',lambda m:setattr(self,'guard',json.loads(m.data)),1)
        self.create_subscription(String,'sim/terminal/status',self.on_terminal,5)
        self.create_subscription(TFMessage,'/tf',self.on_tf,20)
        self.create_timer(.02,self.tick,clock=Clock(clock_type=ClockType.STEADY_TIME))
        self.event('started',case=self.case,state_source='OPENVINS_STEREO_IMU',excitation='PRIVILEGED_DEBUG')
    def elapsed(self):return time.monotonic()-(self.begin or self.started)
    def sample(self,kind,**p):self.stream.write(json.dumps({'kind':kind,'received_wall':time.monotonic(),'elapsed':self.elapsed(),**p})+'\n')
    def event(self,name,**p):
        e=dict(event=name,wall_ns=time.monotonic_ns(),elapsed=self.elapsed(),clock_ns=self.clock,**p);self.events.append(e)
        with (self.out/'m2-events.jsonl').open('a') as f:f.write(json.dumps(e)+'\n')
    def on_clock(self,m):
        t=ns(m.clock)
        if self.first_clock is None:self.first_clock=t
        if t!=self.clock:self.last_clock_wall=time.monotonic()
        self.clock=t
    def sensor(self,key,m):
        stamp=ns(m.header.stamp)*1e-9
        if key in self.sensors and stamp<self.sensors[key]['stamp'] and self.case not in ('clock_rewind','fault_clock_rewind'):self.errors.append('nonmonotonic '+key)
        self.sensors[key]=dict(stamp=stamp,wall=time.monotonic(),count=self.sensors.get(key,{}).get('count',0)+1)
    def state(self,m,truth):
        p=m.pose.pose.position;q=m.pose.pose.orientation;v=m.twist.twist
        value=dict(stamp=ns(m.header.stamp)*1e-9,position=[p.x,p.y,p.z],quaternion=[q.x,q.y,q.z,q.w],velocity=[v.linear.x,v.linear.y,v.linear.z,v.angular.x,v.angular.y,v.angular.z],elapsed=self.elapsed(),wall=time.monotonic())
        if not all(math.isfinite(x) for x in value['position']+value['quaternion']+value['velocity']):self.errors.append('nonfinite state')
        frame=self.prefix+('/truth' if truth else '')
        if m.header.frame_id!=frame+'/odom' or m.child_frame_id!=frame+'/base_link':self.errors.append('incorrect state frame')
        if not truth:
            value['delay_sec']=(self.clock or 0)*1e-9-value['stamp'];value['pose_covariance']=list(m.pose.covariance)
            if self.estimates and value['stamp']<=self.estimates[-1]['stamp']:self.errors.append('estimate stamp not increasing')
            if not np.isfinite(m.pose.covariance).all() or np.min(np.diag(np.array(m.pose.covariance).reshape(6,6)))<0:self.errors.append('invalid estimate covariance')
        (self.truth if truth else self.estimates).append(value);self.sample('truth' if truth else 'estimate',**value)
    def on_imu(self,m):
        self.sensor('imu',m);a=m.linear_acceleration;w=m.angular_velocity
        value=dict(stamp=ns(m.header.stamp)*1e-9,acc=[a.x,a.y,a.z],gyro=[w.x,w.y,w.z],orientation_covariance_0=m.orientation_covariance[0])
        self.imu.append(value);self.sample('imu',**value)
        if m.orientation_covariance[0]!=-1:self.errors.append('truth attitude in IMU')
    def on_health(self,m):
        p=json.loads(m.data);p['elapsed']=self.elapsed();p['wall']=time.monotonic();self.last_health=p;self.health.append(p);self.sample('health',**p);write_json(self.out/'localization-health.json',p)
    def on_terminal(self,m):
        self.terminal=json.loads(m.data);self.terminal_rows.append(dict(elapsed=self.elapsed(),**self.terminal));self.sample('terminal',**self.terminal)
    def on_tf(self,m):
        for t in m.transforms:
            edge=t.header.frame_id+'->'+t.child_frame_id
            self.tf_edges[edge]=self.tf_edges.get(edge,0)+1
    def image(self,m,side):
        self.sensor('image_'+('left','right')[side],m)
        pair=self.pairs.add(side,ns(m.header.stamp),m)
        if pair is None or self.elapsed()<2 or len(self.stereo)>=3 or (self.stereo and self.elapsed()-self.stereo[-1]['elapsed']<4):return
        images=[np.frombuffer(x.data,dtype=np.uint8).reshape(x.height,x.width,3) for x in pair]
        index=len(self.stereo)
        for name,im in zip(('left','right'),images):cv2.imwrite(str(self.out/f'figures/{name}-{index}.png'),cv2.cvtColor(im,cv2.COLOR_RGB2BGR))
        gray=[cv2.cvtColor(x,cv2.COLOR_RGB2GRAY) for x in images];orb=cv2.ORB_create(nfeatures=2000,edgeThreshold=16,fastThreshold=10)
        detected=[orb.detectAndCompute(x,None) for x in gray];matches=[]
        if all(d[1] is not None for d in detected):
            for near in cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(detected[0][1],detected[1][1],k=2):
                if len(near)==2 and near[0].distance<.7*near[1].distance:
                    a=detected[0][0][near[0].queryIdx].pt;b=detected[1][0][near[0].trainIdx].pt
                    if 50<a[0]<590 and 40<a[1]<420 and 0<a[0]-b[0]<120:matches.append([a[0]-b[0],a[1]-b[1]])
        row=dict(elapsed=self.elapsed(),stamp=ns(pair[0].header.stamp)*1e-9,pair_delta_ns=ns(pair[1].header.stamp)-ns(pair[0].header.stamp),matches=len(matches))
        if matches:
            xy=np.array(matches);row.update(disparity_median_px=float(np.median(xy[:,0])),vertical_median_px=float(np.median(abs(xy[:,1]))),vertical_p95_px=float(np.percentile(abs(xy[:,1]),95)))
        if self.case in ('calibration','imu_tilt'):
            projections=[];board_points=[]
            fx,fy,cx,cy=intrinsics(640,480,75)
            for side,image in enumerate(gray):
                found,corners=cv2.findChessboardCornersSB(image,(8,6),cv2.CALIB_CB_NORMALIZE_IMAGE)
                if not found:projections.append(None);board_points.append(None);continue
                y_camera=(-.0725,.0725)[side]
                R=rotation(rpy_quaternion(*[math.radians(v) for v in self.cfg['initial_rpy_enu_deg']]))
                world=np.array([[-1.35+(c+1)*.3,3.945,-(1.1+(r+1)*.3)] for r in range(6) for c in range(8)])
                body=(world-np.array([0.,0.,-2.]))@R-np.array([.16,-y_camera,-.15])
                optical=body[:,[1,2,0]]*np.array([-1.,-1.,1.])
                expected=optical[:,:2]/optical[:,2,None]*np.array([fx,fy])+np.array([cx,cy])
                observed=corners.reshape(-1,2)
                if observed[0,1]>observed[-1,1]:observed=observed[::-1]
                board_points.append(observed)
                projections.append(float(min(np.sqrt(np.mean(np.sum((observed-expected)**2,axis=1))),
                    np.sqrt(np.mean(np.sum((observed[::-1]-expected)**2,axis=1))))))
            row['checkerboard_reprojection_rmse_px']=projections
            row['orb_candidates']=dict(matches=row['matches'],vertical_p95_px=row.get('vertical_p95_px'))
            if all(x is not None for x in board_points):
                delta=board_points[0]-board_points[1]
                row.update(matching_method='identified_checkerboard_corners',matches=len(delta),
                    disparity_median_px=float(np.median(delta[:,0])),vertical_median_px=float(np.median(abs(delta[:,1]))),
                    vertical_p95_px=float(np.percentile(abs(delta[:,1]),95)))
            else:row['matches']=0
        self.stereo.append(row);self.sample('stereo',**row)
    def call(self,action):
        if self.future:return
        self.action=action;self.future=self.client.call_async(Control.Request(run_id=self.out.name,action=action,source='benchmark'));self.event('service_request',action=action)
    def command(self,target):
        self.sequence+=1;m=ControlRequest(run_id=self.out.name,source='benchmark',token=self.token,generation=self.generation,sequence=self.sequence,issued_steady_ns=time.monotonic_ns())
        m.command.header.frame_id=self.prefix+'/base_link';m.command.header.stamp.sec=self.clock//1000000000;m.command.header.stamp.nanosec=self.clock%1000000000
        t=m.command.twist;t.linear.x,t.linear.y,t.linear.z,t.angular.z=map(float,target);self.request_pub.publish(m)
    def inject(self,op,native=False):
        secret=json.loads((self.out/'session.json').read_text())['terminal_secret'];p=dict(run=self.out.name,secret=secret,op=op,sent_ns=time.monotonic_ns())
        (self.native_fixture if native else self.fixture).publish(String(data=json.dumps(p)));self.event('restore' if op in ('restore','resume_clock') else 'injection',op=op)
    def graph(self,filename='graph-inspection.json'):
        topics={}
        for topic in ('/clock',f'/{self.prefix}/state/odometry',f'/{self.prefix}/sim/ground_truth/odometry',f'/{self.prefix}/sensors/imu'):
            topics[topic]=dict(publishers=[dict(name=x.node_name,namespace=x.node_namespace,gid=list(x.endpoint_gid)) for x in self.get_publishers_info_by_topic(topic)],subscribers=[dict(name=x.node_name,namespace=x.node_namespace) for x in self.get_subscriptions_info_by_topic(topic)])
        write_json(self.out/filename,dict(topics=topics,tf_edges=self.tf_edges))
        estimates=topics[f'/{self.prefix}/state/odometry']['publishers'];truthsubs=topics[f'/{self.prefix}/sim/ground_truth/odometry']['subscribers']
        if filename=='graph-before-injection.json':self.pre_injection_estimator_endpoints=estimates
        authority=[x['name'] for x in estimates]==['openvins']
        if self.case=='estimator_kill' and filename=='graph-inspection.json' and self.injected:
            # DDS discovery may retain a dead participant until its lease expires.
            # Require no new endpoint; -9 exit and no new state prove process death.
            authority=not estimates or estimates==self.pre_injection_estimator_endpoints
        return len(topics['/clock']['publishers'])==1 and authority and all(x['name']!='openvins' for x in truthsubs)
    def finish(self):
        thresholds=self.spec['thresholds'];checks={};metrics,data=evaluate(self.truth,self.estimates)
        checks['no_contract_errors']=not self.errors;checks['graph_authority_and_truth_separation']=self.graph()
        expected_edge=self.prefix+'/odom->'+self.prefix+'/base_link'
        checks['unique_estimated_tf']=set(self.tf_edges).issubset({expected_edge}) and (not self.estimates or self.tf_edges.get(expected_edge,0)>0 and max((x.get('tf_verified',0) for x in self.health),default=0)>0 and not any(x.get('foreign_tf_seen',0) for x in self.health))
        checks['exact_stereo_pairs']=bool(self.stereo) and all(x['pair_delta_ns']==0 for x in self.stereo)
        checks['specific_force_only']=bool(self.imu) and all(x['orientation_covariance_0']==-1 for x in self.imu)
        checks['startup_disarmed']=any(e['event']=='ready' and e['startup_disarmed'] for e in self.events)
        checks['cold_start_clock']=self.first_clock is not None and 0<=self.first_clock*1e-9<.1
        checks['cold_start_position']=bool(self.truth) and float(np.linalg.norm(np.array(self.truth[0]['position'])-[0,0,-2]))<.05
        if self.cfg['fixed_fixture'] and self.truth and self.imu:
            q=self.truth[-1]['quaternion'];expected=rotation(q).T@np.array([0,0,9.81]);imu=np.array([x['acc'] for x in self.imu if x['stamp']>2])
            imu_rmse=np.sqrt(np.mean((imu-expected)**2,axis=0));metrics.update(imu_expected_specific_force=expected.tolist(),imu_rmse_m_s2=imu_rmse.tolist())
            checks['fixed_specific_force']=bool(max(imu_rmse)<thresholds['fixed_imu_rmse_m_s2'])
            checks['fixed_estimator_stable']=not any(x['state']=='FAULT' for x in self.health) and (not self.estimates or (
                metrics.get('position_rmse_m',math.inf)<=thresholds['position_rmse_m']
                and max(metrics.get('velocity_rmse_m_s',[math.inf]))<=thresholds['velocity_rmse_m_s']
                and max(metrics.get('attitude_rmse_deg',[math.inf])[:2])<=thresholds['roll_pitch_rmse_deg']))
            if self.case=='calibration':
                fx=intrinsics(640,480,75)[0];disparity=fx*.145/(3.945-.16);metrics['checkerboard_expected_disparity_px']=disparity
                checks['pinhole_projection']=all(all(v is not None and v<thresholds['checkerboard_reprojection_rmse_px'] for v in x['checkerboard_reprojection_rmse_px']) for x in self.stereo)
                checks['metric_stereo_baseline']=all(x['matches']>=thresholds['stereo_min_matches'] and abs(x.get('disparity_median_px',0)-disparity)<thresholds['stereo_disparity_error_px'] for x in self.stereo)
            checks['rectified_epipolar']=all(x['matches']>=thresholds['stereo_min_matches'] and x.get('vertical_median_px',99)<thresholds['stereo_vertical_median_px'] and x.get('vertical_p95_px',99)<thresholds['stereo_vertical_p95_px'] for x in self.stereo)
        elif self.case=='empty_water':
            checks['featureless_not_tracking']=not self.estimates and any(x['state']=='DEGRADED' for x in self.health)
        elif self.case in ('image_dropout','imu_dropout','clock_pause','clock_rewind','estimator_kill'):
            before=[x for x in self.health if x['elapsed']<19];checks['tracking_before_injection']=any(x['state']=='TRACKING' for x in before)
            neutral=next((x for x in self.terminal_rows if int(x['neutral_ns'])*1e-9>=self.injected and all(abs(float(v))<1e-9 for v in x['receiver_setpoint'])),None)
            latency=int(neutral['neutral_ns'])*1e-9-self.injected if neutral else None
            metrics['diagnostic_disarm_to_terminal_neutral_sec']=latency
            checks['diagnostic_disarm_neutralizes']=latency is not None and latency<=thresholds['terminal_neutralization_sec']
            if self.case=='estimator_kill':
                late=[x for x in self.estimates if x['wall']>self.injected+.3];checks['no_old_state_republication']=not late
            else:
                fault=next((x for x in self.health if x['state']=='FAULT' and x['wall']>=self.injected),None)
                latency=fault['wall']-self.injected if fault else None;metrics['fault_detection_wall_sec']=latency
                checks['fault_latched']=bool(fault) and all(x['state']=='FAULT' for x in self.health if x['wall']>fault['wall'])
                checks['fault_deadline']=latency is not None and latency<=thresholds['sensor_fault_detection_sec']
                checks['stale_estimate_stopped']=not any(x['wall']>self.injected+.8 for x in self.estimates)
            checks['no_automatic_rearm']=self.terminal.get('state') in ('DISARMED','FAULT')
        elif self.case!='manual':
            first=next((x['elapsed'] for x in self.health if x['state']=='TRACKING'),None)
            after=[x for x in self.health if 15<x['elapsed']<self.cfg['duration_sec']-1]
            tracking=sum(x['state']=='TRACKING' for x in after)/max(1,len(after));metrics['tracking_fraction_after_15_sec']=tracking
            delay=float(np.percentile([x['delay_sec'] for x in self.estimates],95)) if self.estimates else None;metrics['estimate_delay_p95_sec']=delay
            metrics['first_tracking_elapsed_sec']=first
            checks['initialization']=first is not None and first<=thresholds['initialization_deadline_sec']
            checks['tracking_continuity']=tracking>=thresholds['tracking_fraction']
            checks['position_error']=metrics.get('position_rmse_m',math.inf)<=thresholds['position_rmse_m']
            checks['velocity_error']=max(metrics.get('velocity_rmse_m_s',[math.inf]))<=thresholds['velocity_rmse_m_s']
            att=metrics.get('attitude_rmse_deg',[math.inf]*3);checks['attitude_error']=max(att[:2])<=thresholds['roll_pitch_rmse_deg'] and att[2]<=thresholds['yaw_rmse_deg']
            checks['estimate_latency']=delay is not None and delay<=thresholds['estimate_delay_p95_sec']
        verdict=all(checks.values());self.event('case_complete',passed=verdict)
        result=dict(status='PASS' if verdict else 'FAIL',case=self.case,phase=self.cfg['evaluation_phase'],reason='All case assertions passed' if verdict else 'Failed: '+', '.join(k for k,v in checks.items() if not v),checks=checks,metrics=metrics,stereo=self.stereo,errors=self.errors,
            first_clock_sec=None if self.first_clock is None else self.first_clock*1e-9,sensor_counts={k:v['count'] for k,v in self.sensors.items()},state_source='OPENVINS_STEREO_IMU',truth_access='PRIVILEGED_DEBUG',unverified=['real camera calibration','sensor realism','estimated-state motor control','global heading','position hold','navigation'])
        write_json(self.out/'m2-metrics.json',result);self.stream.flush();render(self.out,self.truth,self.estimates,self.health)
        if self.injected:
            from uw_benchmark.m2_metrics import render_fault
            render_fault(self.out,self.terminal_rows,self.health,self.estimates,self.injected)
        self.done=True;self.result=0 if verdict else 1
    def tick(self):
        if self.done:return
        now=time.monotonic()
        if self.future and self.future.done():
            r=self.future.result();action=self.action;self.future=None;self.event('service_response',action=action,accepted=r.accepted,state=r.state,reason=r.reason)
            if action=='ARM' and r.accepted:self.armed=True;self.token=r.token;self.generation=r.generation;self.begin=now
            elif action=='DISARM':self.disarmed=True;self.armed=False
            elif action=='ARM':self.errors.append('ARM rejected: '+r.reason);self.begin=now
        if self.begin is None:
            if now-self.started>self.cfg['startup_timeout_sec']:
                self.errors.append('startup timeout');self.begin=now-self.cfg['duration_sec'];self.finish();return
            if (len(self.truth)>50 and len(self.imu)>50 and self.last_perception.get('counts',{}).get('stereo',0)>10 and self.guard.get('ready')):
                if not any(e['event']=='ready' for e in self.events):self.event('ready',startup_disarmed=self.guard.get('state')=='DISARMED' and self.terminal.get('state')=='DISARMED')
                if self.cfg['diagnostic_motion']:
                    if not self.future:self.call('ARM')
                else:self.begin=now
            return
        elapsed=self.elapsed();duration=self.cfg['duration_sec']
        if self.truth and self.cfg['diagnostic_motion']:
            x,y,z=self.truth[-1]['position']
            angles=rpy(self.truth[-1]['quaternion'])
            if not (-4.5<z<-.3 and abs(x)<3 and abs(y)<3 and max(abs(angles[0]),abs(angles[1]))<math.radians(self.spec['safety']['roll_pitch_peak_deg'])):
                self.errors.append('safety envelope');self.call('DISARM');self.finish();return
        if self.armed:
            target=[0.,0.,0.,0.]
            if 8<elapsed<18:target=[.12,0,0,0]
            elif 18<=elapsed<26:target=[0,.08,0,0]
            elif 26<=elapsed<32:target=[0,0,0,.08]
            elif 32<=elapsed<38:target=[-.08,0,.03,0]
            self.command(target)
            if elapsed>duration-1 and not self.future and not self.disarmed:self.call('DISARM')
        fault_cases=('image_dropout','imu_dropout','clock_pause','clock_rewind','estimator_kill')
        if self.case in fault_cases and elapsed>20 and self.injected is None:
            if not self.graph('graph-before-injection.json'):self.errors.append('graph invalid before injection')
            if not any(abs(float(v))>.001 for v in self.terminal.get('applied_setpoint',[])):self.errors.append('no nonzero actuation before fault')
            self.injected=now
            if self.case=='estimator_kill':
                entry=next(x for x in [json.loads(s) for s in (self.out/'process-starts.jsonl').read_text().splitlines()] if x['name']=='localization')
                actual=int(Path(f"/proc/{entry['pid']}/stat").read_text().rsplit(') ',1)[1].split()[19])
                if actual!=entry['proc_start_ticks']:raise RuntimeError('PID ownership mismatch')
                write_json(self.out/'expected-exits.json',['localization']);self.event('injection',op='SIGKILL_localization',pid=entry['pid']);os.kill(entry['pid'],signal.SIGKILL)
            else:self.inject({'image_dropout':'drop_images','imu_dropout':'drop_imu','clock_pause':'hold_clock','clock_rewind':'rewind_clock'}[self.case],self.case.startswith('clock_'))
            self.call('DISARM')
        if self.injected and elapsed>23 and not self.restored:
            if self.case in ('image_dropout','imu_dropout'):self.inject('restore')
            elif self.case=='clock_pause':self.inject('resume_clock',True)
            self.restored=True
        if elapsed>duration:self.finish();return
        if not self.injected and elapsed>2:
            if self.count_publishers('/clock')!=1:self.errors.append('clock authority')
            expected={'imu','image_left','image_right','info_left','info_right'}
            if expected!=set(self.sensors) or any(now-x['wall']>2 or abs(x['stamp']-(self.clock or 0)*1e-9)>1 for x in self.sensors.values()):
                self.errors.append('sensor freshness lost');self.call('DISARM');self.finish()


def main(args=None):
    rclpy.init(args=args,signal_handler_options=SignalHandlerOptions.NO);node=Case();stop=[False]
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stop.__setitem__(0,True))
    try:
        while rclpy.ok() and not stop[0] and not node.done:rclpy.spin_once(node,timeout_sec=.05)
    finally:
        result=node.result;node.stream.close();node.destroy_node()
        if rclpy.ok():rclpy.shutdown()
    raise SystemExit(result)
