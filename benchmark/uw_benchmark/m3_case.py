"""Real M3 mission integration. Truth is evaluation-only, never command feedback."""
import json,math,os,signal,time
from pathlib import Path
import numpy as np
import rclpy
from rclpy.action import ActionClient
from rclpy.serialization import serialize_message,deserialize_message
from rclpy.signals import SignalHandlerOptions
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Path as PathMsg
from std_msgs.msg import String
from uw_interfaces.action import ExecuteMission
from uw_interfaces.msg import ControlRequest
from uw_benchmark.m2_case import Case as SensorCase
from uw_benchmark.m2_metrics import evaluate
from uw_runtime.artifacts import write_json
from uw_robot.frames import quaternion_rpy as rpy


class Case(SensorCase):
    def __init__(self):
        super().__init__()
        self.stream.close();(self.out/'m2-samples.jsonl').unlink();self.stream=(self.out/'m3-samples.jsonl').open('w',buffering=1)
        self.action_client=ActionClient(self,ExecuteMission,'mission/execute');self.goal_future=None;self.mission_handle=None;self.result_future=None
        self.action_result=None;self.cancel_future=None;self.nav_rows=[];self.missions=[];self.guard_rows=[];self.goals=[];self.invalid_index=0;self.invalid_future=None;self.invalid_results=[]
        self.feedback_count=0;self.notready_future=None;self.restart_replayed=False;self.controller_rows=[]
        self.previous_request=None;self.replayed=False;self.nav={};self.initial_disarmed=False;self.pre_fault_nonzero=False;self.pre_fault_physics=0
        self.spec_case=self.spec['cases'].get(self.case,{})
        self.create_subscription(PathMsg,'navigation/path',lambda m:setattr(self,'goals',list(m.poses)),1)
        self.create_subscription(String,'navigation/status',self.on_nav,5)
        self.create_subscription(String,'mission/status',lambda m:self.record('mission',m,self.missions),5)
        self.create_subscription(String,'control/status',lambda m:self.record('guard',m,self.guard_rows),5)
        self.create_subscription(ControlRequest,'control/request',self.on_request,1)
        self.create_subscription(String,'control/controller_status',lambda m:self.record('controller',m,self.controller_rows),5)
    def on_request(self,m):
        self.previous_request=m
        path=self.out/'first-request.cdr'
        if not path.exists() and m.run_id==self.out.name:path.write_bytes(serialize_message(m))
    def feedback(self,m):
        self.feedback_count+=1;v=m.feedback;self.sample('action_feedback',state=v.state,waypoint_index=v.waypoint_index,distance_m=v.distance_m,elapsed_sec=v.elapsed_sec)
    def event(self,name,**p):
        if name=='started':p.update(excitation='NONE',estimated_state_control=True)
        e=dict(event=name,wall_ns=time.monotonic_ns(),elapsed=self.elapsed(),clock_ns=self.clock,**p);self.events.append(e)
        with (self.out/'m3-events.jsonl').open('a') as f:f.write(json.dumps(e)+'\n')
    def record(self,kind,m,rows):
        p=json.loads(m.data);p['elapsed']=self.elapsed();p['received_wall']=time.monotonic();rows.append(p);self.sample(kind,**p)
    def on_nav(self,m):self.nav=json.loads(m.data);self.record('navigation',m,self.nav_rows)
    def goal(self,mission='benchmark_mission'):
        g=ExecuteMission.Goal(run_id=self.out.name,mission_id=mission,authorize_arm=True,timeout_sec=float(self.spec_case.get('mission_timeout_sec',45)))
        points=self.spec_case.get('waypoints',[[.8,0,0,0]])
        for x,y,z,a in points:
            p=PoseStamped();p.header.frame_id=self.prefix+'/mission_start';p.pose.position.x=float(x);p.pose.position.y=float(y);p.pose.position.z=float(z)
            p.pose.orientation.z=math.sin(a/2);p.pose.orientation.w=math.cos(a/2);g.waypoints.append(p)
        return g
    def kill(self,name):
        rows=[json.loads(s) for s in (self.out/'process-starts.jsonl').read_text().splitlines()]
        entry=next(x for x in rows if x['name']==name)
        actual=int(Path(f"/proc/{entry['pid']}/stat").read_text().rsplit(') ',1)[1].split()[19])
        if actual!=entry['proc_start_ticks']:raise RuntimeError('PID ownership mismatch')
        write_json(self.out/'expected-exits.json',[name]);self.event('injection',op='SIGKILL_'+name,pid=entry['pid']);os.kill(entry['pid'],signal.SIGKILL)
    def validate_goals(self):
        if self.invalid_future and self.invalid_future.done():
            accepted=self.invalid_future.result().accepted;self.invalid_results.append(not accepted);self.event('invalid_goal_result',index=self.invalid_index-1,accepted=accepted);self.invalid_future=None
        if self.invalid_future:return
        variants=['no_authorization','wrong_run','wrong_frame','nonfinite','orientation','outside','timeout','empty']
        if self.invalid_index>=len(variants):return
        name=variants[self.invalid_index];g=self.goal('invalid_'+name)
        if name=='no_authorization':g.authorize_arm=False
        elif name=='wrong_run':g.run_id='stale_run'
        elif name=='wrong_frame':g.waypoints[0].header.frame_id='world'
        elif name=='nonfinite':g.waypoints[0].pose.position.x=float('nan')
        elif name=='orientation':g.waypoints[0].pose.orientation.x=.2
        elif name=='outside':g.waypoints[0].pose.position.x=2.
        elif name=='timeout':g.timeout_sec=float('inf')
        elif name=='empty':g.waypoints=[]
        self.invalid_index+=1;self.invalid_future=self.action_client.send_goal_async(g)
    def tick(self):
        if self.done:return
        now=time.monotonic()
        if self.begin is None:
            if self.case=='bootstrap' and self.notready_future is None and self.action_client.server_is_ready() and not self.guard.get('ready'):
                self.notready_future=self.action_client.send_goal_async(self.goal('before_ready'))
            if self.guard and self.terminal and not self.initial_disarmed:self.initial_disarmed=self.guard.get('state')=='DISARMED' and self.terminal.get('state')=='DISARMED'
            if now-self.started>self.cfg['startup_timeout_sec']:
                self.errors.append('startup timeout');self.begin=now-self.cfg['duration_sec'];self.finish();return
            if self.guard.get('ready') and self.action_client.server_is_ready() and self.estimates and self.truth:
                self.begin=now;self.event('ready',startup_disarmed=self.initial_disarmed)
            return
        elapsed=self.elapsed()
        if self.case=='invalid_goals':self.validate_goals()
        elif self.case not in ('manual','bootstrap') and self.goal_future is None:
            g=self.goal();self.goals=list(g.waypoints);self.goal_future=self.action_client.send_goal_async(g,feedback_callback=self.feedback);self.event('mission_sent',waypoints=[[p.pose.position.x,p.pose.position.y,p.pose.position.z] for p in self.goals])
        if self.goal_future and self.goal_future.done() and self.mission_handle is None:
            self.mission_handle=self.goal_future.result();self.event('mission_response',accepted=self.mission_handle.accepted)
            if self.mission_handle.accepted:self.result_future=self.mission_handle.get_result_async()
            else:self.errors.append('mission rejected')
        if self.result_future and self.result_future.done() and self.action_result is None:
            response=self.result_future.result();r=response.result;self.action_result=dict(status=response.status,outcome=r.outcome,reason=r.reason,completed=r.completed_waypoints,neutral=r.terminal_neutral_verified)
            self.event('mission_result',**self.action_result)
        if self.case=='restart_replay' and elapsed>2 and not self.restart_replayed:
            path=self.out/'previous-request.cdr'
            if path.exists():
                old=deserialize_message(path.read_bytes(),ControlRequest);self.request_pub.publish(old);self.event('previous_run_request_replayed',previous_run=old.run_id);self.restart_replayed=True
        if self.case=='cancel' and elapsed>6 and self.mission_handle and self.mission_handle.accepted and self.cancel_future is None:
            self.injected=now;self.pre_fault_nonzero=any(abs(float(v))>.001 for v in self.terminal.get('applied_setpoint',[]))
            self.cancel_future=self.mission_handle.cancel_goal_async();self.event('injection',op='action_cancel')
        if self.case in ('mission_1','cancel') and elapsed>3 and not hasattr(self,'busy_future'):
            self.busy_future=self.action_client.send_goal_async(self.goal('competing_mission'));self.event('competing_goal_sent')
        if self.case.startswith('fault_') and elapsed>6 and self.injected is None:
            self.pre_fault_nonzero=any(abs(float(v))>.001 for v in self.terminal.get('applied_setpoint',[]));self.pre_fault_physics=int(self.terminal.get('physics_ns',0))
            self.graph('graph-before-injection.json');self.injected=now
            kind=self.case.removeprefix('fault_')
            if kind in ('tasks','navigation','guard','controller','actuator_adapter','localization','rviz'):self.kill(kind)
            else:self.inject({'images':'drop_images','imu':'drop_imu','clock_pause':'hold_clock','clock_rewind':'rewind_clock'}[kind],kind.startswith('clock_'))
        if self.injected and now-self.injected>3 and not self.restored:
            if self.case in ('fault_images','fault_imu'):self.inject('restore')
            elif self.case=='fault_clock_pause':self.inject('resume_clock',True)
            self.restored=True
            if self.previous_request:self.request_pub.publish(self.previous_request);self.replayed=True;self.event('old_request_replayed')
        if self.case=='cancel' and self.action_result and not hasattr(self,'replay_goal_future'):
            self.replay_goal_future=self.action_client.send_goal_async(self.goal());self.event('old_mission_replayed')
        if self.truth and self.case!='manual':
            x,y,z=self.truth[-1]['position'];angles=rpy(self.truth[-1]['quaternion'])
            if not (-4.5<z<-.3 and max(abs(x),abs(y))<2 and max(abs(angles[0]),abs(angles[1]))<math.radians(25)):
                self.errors.append('evaluation safety envelope');self.call('FAULT');self.finish();return
        if elapsed>2 and (not self.injected or self.case=='fault_rviz'):
            if self.count_publishers('/clock')!=1:self.errors.append('clock authority')
            if set(self.sensors)!={'imu','image_left','image_right','info_left','info_right'} or any(now-x['wall']>2 or abs(x['stamp']-(self.clock or 0)*1e-9)>1 for x in self.sensors.values()):
                self.errors.append('sensor freshness lost');self.call('FAULT');self.finish();return
        if elapsed>self.cfg['duration_sec']:self.finish()
    def graph(self,filename='graph-inspection.json'):
        topics={}
        for topic in ('/clock',f'/{self.prefix}/state/odometry',f'/{self.prefix}/sim/ground_truth/odometry',f'/{self.prefix}/control/request'):
            topics[topic]=dict(publishers=[dict(name=x.node_name,gid=list(x.endpoint_gid)) for x in self.get_publishers_info_by_topic(topic)],subscribers=[x.node_name for x in self.get_subscriptions_info_by_topic(topic)])
        write_json(self.out/filename,dict(topics=topics,tf_edges=self.tf_edges))
        forbidden={'openvins','navigation','missions','control_guard','body_velocity_controller','rtabmap'}
        return len(topics['/clock']['publishers'])==1 and not forbidden.intersection(topics[f'/{self.prefix}/sim/ground_truth/odometry']['subscribers'])
    def finish(self):
        if self.done:return
        th=self.spec['thresholds'];metrics,data=evaluate(self.truth,self.estimates)
        checks=dict(no_contract_errors=not self.errors,graph_truth_isolation=self.graph(),startup_disarmed=self.initial_disarmed,
            cold_clock=self.first_clock is not None and self.first_clock<100_000_000,
            cold_position=bool(self.truth) and np.linalg.norm(np.array(self.truth[0]['position'])-getattr(self,'expected_initial_position',[0,0,-2]))<.05,
            estimated_feedback=self.guard.get('state_source')=='OPENVINS_STEREO_IMU',
            controller_integral_cold=bool(self.controller_rows) and self.controller_rows[0].get('integral')==[0.]*4,
            no_foreign_tf=not any(x.get('foreign_tf_seen',0) for x in self.health))
        active=[x for x in self.controller_rows if x.get('generation',0)>0]
        if active:
            metrics['control_request_age_p95_sec']=float(np.percentile([x['request_age_sec'] for x in active],95))
            metrics['control_period_p95_sec']=float(np.percentile([x['period_sec'] for x in active],95))
            checks['control_latency']=metrics['control_request_age_p95_sec']<=th['control_request_age_p95_sec']
        metrics['first_estimated_state_sec']=self.estimates[0]['stamp'] if self.estimates else None
        metrics['feedback_count']=self.feedback_count
        if self.cfg['visualization']=='rviz' and self.case!='fault_rviz':
            checks['rviz_subscribes_mission_status']=any(x.node_name=='rviz2' for x in self.get_subscriptions_info_by_topic(f'/{self.prefix}/mission/status_marker'))
        group=self.spec_case.get('group')
        if group=='missions' or self.case.startswith('load_') or self.case=='fault_rviz':
            checks.update(mission_succeeded=self.action_result is not None and self.action_result['outcome']=='SUCCEEDED' and self.action_result['neutral'],
                visual_tracking=any(x['state']=='TRACKING' for x in self.health),
                estimate_position=metrics.get('position_rmse_m',99)<=th['estimate_position_rmse_m'],
                estimate_velocity=max(metrics.get('velocity_rmse_m_s',[99]))<=th['estimate_velocity_rmse_m_s'])
            events_path=self.out/'mission-events.jsonl';events=[json.loads(x) for x in events_path.read_text().splitlines()] if events_path.exists() else []
            reached=[e for e in events if e['event']=='waypoint_reached'];errors=[];yaw_errors=[]
            if data:
                R=np.array([[math.cos(data['yaw_offset']),-math.sin(data['yaw_offset']),0],[math.sin(data['yaw_offset']),math.cos(data['yaw_offset']),0],[0,0,1]])
                translation=np.array(metrics['alignment_translation'])
                for e in reached:
                    nearest=min(self.truth,key=lambda x:abs(x['wall']-e['wall_ns']*1e-9));p=self.goals[e['index']].pose.position
                    errors.append(float(np.linalg.norm(np.array(nearest['position'])-(R@np.array([p.x,p.y,p.z])+translation))))
                    q=self.goals[e['index']].pose.orientation;delta=rpy(nearest['quaternion'])[2]-rpy([q.x,q.y,q.z,q.w])[2]-data['yaw_offset'];yaw_errors.append(abs(math.atan2(math.sin(delta),math.cos(delta))))
            metrics['true_waypoint_errors_m']=errors;metrics['true_waypoint_yaw_errors_rad']=yaw_errors
            checks['true_waypoint_yaw']=bool(yaw_errors) and max(yaw_errors)<=th['true_waypoint_yaw_rad']
            checks['true_waypoint_accuracy']=len(errors)==len(self.goals) and bool(errors) and max(errors)<=th['true_waypoint_error_m']
            metrics['mission_result']=self.action_result
            checks['action_feedback']=self.feedback_count>10
            checks['attitude_accuracy']=max(metrics.get('attitude_rmse_deg',[99,99])[:2])<=th['roll_pitch_error_rmse_deg']
            if self.case=='restart_replay':checks['previous_run_request_rejected']=self.restart_replayed and any(x.get('last_reject')=='authorization_mismatch' for x in self.guard_rows)
        elif self.case=='bootstrap':
            checks['no_arm_without_mission']=all(x['state']=='DISARMED' for x in self.guard_rows) and bool(self.estimates)
            checks['not_ready_rejected']=self.notready_future is not None and self.notready_future.done() and not self.notready_future.result().accepted
        elif self.case=='invalid_goals':checks['all_invalid_rejected']=len(self.invalid_results)==8 and all(self.invalid_results);checks['no_arm']=self.guard.get('state')=='DISARMED'
        elif self.case=='timeout':checks['timeout_aborted']=self.action_result is not None and self.action_result['outcome']=='ABORTED' and self.action_result['reason']=='mission_timeout' and self.action_result['neutral']
        elif self.case=='cancel':
            checks['action_canceled']=self.action_result is not None and self.action_result['outcome']=='CANCELED' and self.action_result['status']==5 and self.action_result['neutral']
            checks['old_mission_rejected']=hasattr(self,'replay_goal_future') and self.replay_goal_future.done() and not self.replay_goal_future.result().accepted
        if hasattr(self,'busy_future'):checks['competing_goal_rejected']=self.busy_future.done() and not self.busy_future.result().accepted
        if self.injected and self.case!='fault_rviz':
            neutral=next((x for x in self.terminal_rows if int(x['neutral_ns'])*1e-9>=self.injected and all(abs(float(v))<1e-9 for v in x['receiver_setpoint'])),None)
            latency=int(neutral['neutral_ns'])*1e-9-self.injected if neutral else None;metrics['injection_to_terminal_neutral_sec']=latency
            checks['nonzero_before_injection']=self.pre_fault_nonzero
            checks['terminal_deadline']=latency is not None and 0<=latency<=th['terminal_neutral_sec']
            checks['no_rearm_after_restore_replay']=self.terminal.get('state') in ('DISARMED','FAULT') and not any(x['state']=='ARMED' for x in self.terminal_rows if int(x['wall_ns'])*1e-9>self.injected+.6)
            if self.case.startswith('fault_'):
                checks['fault_latched']=self.terminal.get('state')=='FAULT'
                checks['physics_continued']=int(self.terminal.get('physics_ns',0))>self.pre_fault_physics+1_000_000_000
                if self.case!='fault_tasks':checks['mission_aborted']=self.action_result is not None and self.action_result['outcome']=='ABORTED'
        if self.case=='manual':checks['manual_observation']=True
        checks={k:bool(v) for k,v in checks.items()};passed=all(checks.values());self.event('case_complete',passed=passed)
        write_json(self.out/'m3-metrics.json',dict(status='PASS' if passed else 'FAIL',case=self.case,phase=self.cfg['evaluation_phase'],checks=checks,metrics=metrics,errors=self.errors,
            action_result=self.action_result,reason='All case assertions passed' if passed else 'Failed: '+', '.join(k for k,v in checks.items() if not v),
            sensor_counts={k:v['count'] for k,v in self.sensors.items()},state_source='OPENVINS_STEREO_IMU',evaluation_truth='PRIVILEGED_DEBUG',
            unverified=['obstacle avoidance','global localization','mapping','real hardware','open-water generalization']))
        self.stream.flush()
        from uw_benchmark.m3_metrics import render
        render(self.out,self.truth,self.estimates,self.nav_rows,self.terminal_rows,self.health,self.injected)
        self.done=True;self.result=0 if passed else 1


def main(args=None):
    rclpy.init(args=args,signal_handler_options=SignalHandlerOptions.NO);node=Case();stop=[False]
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stop.__setitem__(0,True))
    try:
        while rclpy.ok() and not stop[0] and not node.done:rclpy.spin_once(node,timeout_sec=.05)
    finally:result=node.result;node.stream.close();node.destroy_node();rclpy.try_shutdown()
    raise SystemExit(result)
