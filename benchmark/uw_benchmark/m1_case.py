"""Finite simulation research cases with native receiver evidence and explicit ARM."""
import copy,json,math,os,signal,time
from pathlib import Path
import numpy as np
import yaml
import rclpy
from rclpy.signals import SignalHandlerOptions
from rclpy.node import Node
from rclpy.clock import Clock,ClockType
from nav_msgs.msg import Odometry,Path as PathMsg
from geometry_msgs.msg import PoseStamped
from rosgraph_msgs.msg import Clock as ClockMsg
from std_msgs.msg import String
from visualization_msgs.msg import Marker
from diagnostic_msgs.msg import DiagnosticArray,DiagnosticStatus,KeyValue
from uw_interfaces.msg import ControlRequest,ActuatorOutput,AuthorizedCommand
from uw_interfaces.srv import Control
from uw_robot.frames import quaternion_rpy as rpy


def stamp_ns(s):return s.sec*1_000_000_000+s.nanosec


def native_numbers(p):
    p=dict(p)
    for key in ('wall_ns','fault_ns','neutral_ns','applied_ns','physics_ns','clock_ns','generation','deadline_ns','request_seq','output_seq'):
        p[key]=int(p[key])
    for key in ('receiver_setpoint','applied_setpoint','rpm','thrust_N','reaction_torque_Nm'):p[key]=[float(x) for x in p[key]]
    return p


class Case(Node):
    def __init__(self):
        super().__init__('m1_case')
        self.folder=Path(self.declare_parameter('run_dir','').value);self.config=yaml.safe_load((self.folder/'resolved_config.yaml').read_text())
        self.names=[x['name'] for x in yaml.safe_load((self.folder/'thrusters.yaml').read_text())['thrusters']]
        self.specification=yaml.safe_load((self.folder/'acceptance.yaml').read_text())
        self.case=self.config['case_id'];self.namespace=self.config['namespace'];self.started=time.monotonic()
        self.clock=0;self.first_clock=None;self.guard={};self.terminal={};self.state=None;self.states=[];self.feedback=[];self.outputs=[];self.periods=[]
        self.events=[];self.arm_time=None;self.token='';self.active_source='benchmark';self.generation=0;self.sequence=0;self.future=None;self.pending_action=None
        self.done=False;self.disarmed=False;self.injected=None;self.last_message=None;self.target=[0.]*4;self.extra={}
        self.stream=(self.folder/'control-samples.jsonl').open('w',buffering=1)
        self.publisher=self.create_publisher(ControlRequest,'control/request',1)
        self.second_candidate=self.create_publisher(ControlRequest,'control/request',1) if self.case.startswith('authority_') else None
        self.fixture=self.create_publisher(String,'sim/terminal/fixture',1)
        self.observation_fixture=self.create_publisher(String,'sim/observation/fixture',1)
        self.native_replay=None;self.last_native=None;self.replay_count=0
        self.create_subscription(String,'sim/terminal/input',self.on_native,1)
        self.restart_replay=None;self.restart_replay_at=None;self.restart_checked=False
        self.marker=self.create_publisher(Marker,'control/status_marker',1)
        self.diagnostics=self.create_publisher(DiagnosticArray,'diagnostics',1)
        self.trajectory=self.create_publisher(PathMsg,'control/trajectory',1);self.path=PathMsg();self.path.header.frame_id=self.namespace+'/odom'
        self.client=self.create_client(Control,'control/authority')
        self.create_subscription(ClockMsg,'/clock',self.on_clock,1)
        self.create_subscription(Odometry,'state/odometry',self.on_state,5)
        self.create_subscription(String,'control/status',self.on_guard,1)
        self.create_subscription(String,'sim/terminal/status',self.on_terminal,5)
        self.create_subscription(String,'control/controller_status',self.on_controller,5)
        self.create_subscription(ActuatorOutput,'control/output',self.on_output,5)
        if self.case=='manual':self.create_subscription(AuthorizedCommand,'control/approved',self.on_manual_target,1)
        self.create_timer(0.02,self.tick,clock=Clock(clock_type=ClockType.STEADY_TIME))
        self.event('started',case=self.case,phase=self.config['evaluation_phase'])

    def event(self,name,**data):
        value=dict(event=name,wall_ns=time.monotonic_ns(),clock_ns=self.clock,**data);self.events.append(value)
        with (self.folder/'control-events.jsonl').open('a') as f:f.write(json.dumps(value)+'\n')

    def sample(self,kind,data):
        self.stream.write(json.dumps(dict(kind=kind,received_ns=time.monotonic_ns(),**data))+'\n')

    def on_native(self,m):
        self.last_native=m.data
        p=json.loads(m.data)
        if p.get('run')==self.folder.name and any(abs(v)>.02 for v in p.get('values',[])) and not (self.folder/'first-native-command.json').exists():
            (self.folder/'first-native-command.json').write_text(m.data+'\n')

    def on_manual_target(self,m):
        t=m.request.command.twist
        self.target=[t.linear.x,t.linear.y,t.linear.z,t.angular.z]

    def on_guard(self,m):
        self.guard=json.loads(m.data);self.sample('guard',self.guard)
        marker=Marker();marker.header.frame_id=self.namespace+'/odom';marker.type=Marker.TEXT_VIEW_FACING
        marker.ns='control_state';marker.id=0;marker.action=Marker.ADD;marker.pose.orientation.w=1.
        if self.state:marker.pose.position.x,marker.pose.position.y,marker.pose.position.z=self.state['position']
        marker.pose.position.z+=.7
        marker.scale.z=.07;marker.color.a=1.;marker.color.g=1. if self.guard['state']=='ARMED' else .5
        marker.color.r=1. if self.guard['state']=='FAULT' else .2
        marker.text=f"{self.guard['state']}\n{self.guard['source']} / arm {self.guard['generation']}\nPRIVILEGED_DEBUG"
        self.marker.publish(marker)
        diag=DiagnosticStatus(name=self.namespace+'/m1_control',hardware_id='stonefish_simulation',
            level=DiagnosticStatus.ERROR if self.guard['state']=='FAULT' else DiagnosticStatus.OK,
            message=self.guard['state']+': '+self.guard['reason'],values=[KeyValue(key='state_source',value='PRIVILEGED_DEBUG')])
        self.diagnostics.publish(DiagnosticArray(status=[diag]))

    def on_clock(self,m):
        self.clock=stamp_ns(m.clock)
        if self.first_clock is None:self.first_clock=self.clock

    def on_state(self,m):
        p=m.pose.pose.position;q=m.pose.pose.orientation;v=m.twist.twist
        angles=list(rpy([q.x,q.y,q.z,q.w]))
        self.state=dict(wall=time.monotonic(),stamp=stamp_ns(m.header.stamp)*1e-9,
            position=[p.x,p.y,p.z],velocity=[v.linear.x,v.linear.y,v.linear.z,v.angular.x,v.angular.y,v.angular.z],rpy=angles,
            target=list(self.target))
        self.states.append(self.state);self.sample('state',self.state)
        if len(self.states)%10==0:
            self.path.header.stamp=m.header.stamp;self.path.poses.append(PoseStamped(header=m.header,pose=m.pose.pose));self.trajectory.publish(self.path)

    def on_terminal(self,m):
        self.terminal=native_numbers(json.loads(m.data));self.feedback.append(self.terminal);self.sample('terminal',self.terminal)

    def on_output(self,m):
        def w(x):return [x.force.x,x.force.y,x.force.z,x.torque.x,x.torque.y,x.torque.z]
        value=dict(wall=time.monotonic(),setpoint=list(m.setpoint),requested_wrench=w(m.requested_wrench),
                   predicted_wrench=w(m.predicted_wrench),saturated=m.saturated,
                   request_age_sec=(time.monotonic_ns()-m.authorization.request.issued_steady_ns)*1e-9)
        self.outputs.append(value);self.sample('output',value)

    def on_controller(self,m):
        p=json.loads(m.data);self.periods.append(p);self.sample('controller',p)

    def call(self,action,source='benchmark'):
        if self.future:return
        self.pending_action=action;self.future=self.client.call_async(Control.Request(run_id=self.folder.name,action=action,source=source))
        self.event('service_request',action=action,source=source)

    def request(self,target,probe=None):
        self.sequence+=1;m=ControlRequest();m.run_id=self.folder.name;m.source=self.active_source;m.token=self.token
        m.generation=self.generation;m.sequence=self.sequence;m.issued_steady_ns=time.monotonic_ns()
        m.command.header.frame_id=self.namespace+'/base_link';m.command.header.stamp.sec=self.clock//1_000_000_000;m.command.header.stamp.nanosec=self.clock%1_000_000_000
        t=m.command.twist;t.linear.x,t.linear.y,t.linear.z,t.angular.z=map(float,target)
        if probe is not None:m.actuator_probe.name=self.names;m.actuator_probe.position=probe
        self.publisher.publish(m);self.last_message=copy.deepcopy(m)

    def finish(self,passed,reason,**details):
        if self.done:return
        self.event('case_complete',passed=passed,reason=reason)
        result=dict(status='PASS' if passed else 'FAIL',case_id=self.case,evaluation_phase=self.config['evaluation_phase'],
            reason=reason,first_clock_sec=None if self.first_clock is None else self.first_clock*1e-9,
            wall_duration_sec=time.monotonic()-self.started,state_source='PRIVILEGED_DEBUG',
            terminal_state=self.terminal.get('state'),events=self.events,**details)
        (self.folder/'control-metrics.json').write_text(json.dumps(result,indent=2)+'\n')
        self.stream.flush()
        from uw_benchmark.plots import render
        render(self.folder)
        self.done=True;self.result=0 if passed else 1

    def tick(self):
        if self.done:return
        now=time.monotonic()
        if self.future and self.future.done():
            res=self.future.result();action=self.pending_action;self.future=None
            self.event('service_response',action=action,accepted=res.accepted,state=res.state,reason=res.reason,generation=res.generation)
            if self.extra.pop('expect_unready_rejection',False):
                if res.accepted:self.finish(False,'ARM incorrectly accepted before readiness');return
                self.extra['unready_rejected']=res.reason
            elif action=='ARM':
                if not res.accepted:self.finish(False,'Explicit ARM rejected: '+res.reason);return
                self.token=res.token;self.active_source=res.source;self.generation=res.generation
                if self.arm_time is None:self.arm_time=now
            elif action=='DISARM':self.disarmed=True
        if self.case=='manual':
            if now-self.started>self.config['duration_sec']:self.finish(True,'Manual observation session finished')
            return
        if self.arm_time is None:
            if self.case.startswith('authority_') and 'unready_rejected' not in self.extra and not self.future and self.client.service_is_ready():
                if self.guard.get('ready'):self.finish(False,'Missed pre-readiness injection window');return
                self.extra['expect_unready_rejection']=True;self.call('ARM');self.request([0.]*4,[0.]*8 if self.config['control_mode']=='actuator_probe' else None)
                return
            if now-self.started>self.config['startup_timeout_sec']:self.finish(False,'M1 readiness timeout',guard=self.guard,terminal=self.terminal.get('state'));return
            if (self.guard.get('ready') or self.restart_replay is not None) and self.client.service_is_ready() and not self.future:
                if self.guard.get('state')!='DISARMED' or self.terminal.get('state')!='DISARMED':self.finish(False,'Startup was not DISARMED');return
                if any(abs(v)>1e-12 for v in self.terminal['applied_setpoint']):self.finish(False,'Nonzero initial native setpoint');return
                if self.config['control_mode']=='body_velocity' and (not self.periods or any(self.periods[-1]['integral']) or any(self.periods[-1]['attitude_integral'])):self.finish(False,'Initial controller integrals not zero');return
                if not self.restart_checked:
                    previous=self.folder/'previous-native-command.json'
                    if previous.exists():
                        if self.restart_replay_at is None:
                            self.restart_replay=self.create_publisher(String,'sim/terminal/input',1)
                            self.restart_replay_at=now;self.event('previous_run_replay',previous_run=json.loads(previous.read_text())['run'])
                        self.restart_replay.publish(String(data=previous.read_text()))
                        if now-self.restart_replay_at<.3:return
                        self.destroy_publisher(self.restart_replay);self.restart_replay=None
                    self.restart_checked=True
                    self.event('cold_start_verified',first_clock_sec=self.first_clock*1e-9,integrals_zero=True,applied_zero=True,previous_run_replayed=previous.exists())
                    return
                self.event('ready',initial_state=self.state,initial_setpoint=self.terminal['applied_setpoint'])
                self.call('ARM')
            return
        elapsed=now-self.arm_time
        if self.case.startswith('authority_'):
            self.authority_case(elapsed);return
        if self.case.startswith('probe_'):
            self.probe_case(elapsed);return
        if self.state and not self.config['fixed_fixture']:
            p=self.state['position'];a=self.state['rpy'];v=self.state['velocity']
            if not (-4.5<p[2]<-0.3 and max(abs(x) for x in a[:2])<math.radians(25) and max(abs(x) for x in p[:2])<8 and max(abs(x) for x in v[:3])<1.2):
                self.call('DISARM');self.finish(False,'Safety envelope exceeded',state=self.state);return
        if self.case.startswith('fault_'):
            self.fault_case(elapsed);return
        self.velocity_case(elapsed)

    def authority_case(self,t):
        checks=[('wrong_run','authorization_mismatch'),('wrong_frame','wrong_frame'),('nan','nonfinite_twist'),
                ('inf','nonfinite_twist'),('expired','expired_ros_stamp'),('future','future_ros_stamp'),
                ('roll','unsupported_roll_pitch_rate'),('pitch','unsupported_roll_pitch_rate'),
                ('channel','invalid_channels'),('duplicate','invalid_channels'),('missing','invalid_channels'),
                ('limit','request_limit_exceeded')]
        probe_mode=self.config['control_mode']=='actuator_probe'
        if not probe_mode:checks=[x for x in checks if x[0] not in ('channel','duplicate','missing')]
        x=self.extra
        if 'checks' not in x:
            x.update(checks=[],check_index=0,next_check=.3,old_authorization=None)
            x['not_armed_rejected']=self.guard.get('rejected',0)>0
        if self.guard.get('state')=='ARMED':
            self.request([0.]*4,[0.]*8 if probe_mode else None)
            if x['old_authorization'] is None:x['old_authorization']=copy.deepcopy(self.last_message)
        if x['check_index']<len(checks):
            name,expected=checks[x['check_index']]
            if 'waiting_reject' in x:
                if self.guard.get('rejected',0)>x['waiting_reject']:
                    actual=self.guard['last_reject'];x['checks'].append(dict(check=name,expected=expected,actual=actual,passed=actual==expected))
                    self.event('invalid_request_result',check=name,expected=expected,actual=actual)
                    if actual!=expected:self.finish(False,'Wrong rejection reason',checks=x['checks']);return
                    x.pop('waiting_reject');x['check_index']+=1;x['next_check']=t+.1
                elif t>x['check_sent']+.2:self.finish(False,'Invalid request was not rejected',check=name);return
            elif t>=x['next_check'] and self.last_message:
                m=copy.deepcopy(self.last_message);m.sequence+=1
                if name=='wrong_run':m.run_id='previous-run'
                elif name=='wrong_frame':m.command.header.frame_id=self.namespace+'/odom'
                elif name=='nan':m.command.twist.linear.x=float('nan')
                elif name=='inf':m.command.twist.linear.x=float('inf')
                elif name in ('expired','future'):
                    stamp=self.clock+(-500_000_000 if name=='expired' else 100_000_000)
                    m.command.header.stamp.sec=stamp//1_000_000_000;m.command.header.stamp.nanosec=stamp%1_000_000_000
                elif name=='roll':m.command.twist.angular.x=.01
                elif name=='pitch':m.command.twist.angular.y=.01
                elif name=='channel':m.actuator_probe.name[0]='not-a-channel'
                elif name=='duplicate':m.actuator_probe.name[0]=m.actuator_probe.name[1]
                elif name=='missing':m.actuator_probe.name.pop()
                elif name=='limit':
                    if probe_mode:m.actuator_probe.position[0]=.16
                    else:m.command.twist.linear.x=.41
                x['waiting_reject']=self.guard.get('rejected',0);x['check_sent']=t
                self.second_candidate.publish(m);self.event('invalid_request_sent',check=name)
            return
        if 'switch' not in x:
            x['switch']='selecting';self.call('SELECT_SOURCE','cli');return
        if x['switch']=='selecting' and not self.future and self.guard.get('source')=='cli' and self.terminal.get('state')=='DISARMED':
            x['switch']='arming';self.call('ARM','cli');return
        if x['switch']=='arming' and not self.future and self.active_source=='cli' and self.terminal.get('state')=='ARMED':
            x['switch']='replay';x['replay_start']=t;x['replay_rejections']=self.guard.get('rejected',0)
        if x['switch']=='replay':
            old=copy.deepcopy(x['old_authorization']);old.issued_steady_ns=time.monotonic_ns()
            old.command.header.stamp=self.last_message.command.header.stamp;old.sequence=self.sequence+100
            self.second_candidate.publish(old)
            if t-x['replay_start']>1:
                x['switch']='disarming';x['replay_pass']=(self.guard.get('rejected',0)>x['replay_rejections'] and self.guard.get('last_reject')=='authorization_mismatch' and self.guard.get('state')=='ARMED')
                self.call('DISARM')
        if x['switch']=='disarming' and self.terminal.get('state')=='DISARMED':
            passed=bool(x.get('unready_rejected') and x['not_armed_rejected'] and all(v['passed'] for v in x['checks']) and x['replay_pass'])
            self.finish(passed,'Explicit readiness, invalid requests, source switch and old authorization',
                checks=x['checks'],not_ready_rejection=x.get('unready_rejected'),not_armed_rejected=x['not_armed_rejected'],
                old_source_replay_rejected=x['replay_pass'],final_generation=self.generation)

    def probe_case(self,t):
        index=int(self.case.split('_')[1]);probe=[0.]*8
        if 1<=t<3:probe[index]=0.12
        elif 4<=t<6:probe[index]=-0.12
        if t<8:self.request([0.]*4,probe)
        elif not self.disarmed and not self.future:self.call('DISARM')
        if t>=9:
            p=yaml.safe_load((self.folder/'thrusters.yaml').read_text());item=p['thrusters'][index]
            native_sign=(-1 if item['inverted'] else 1)*(1 if item['right_handed'] else -1)
            windows={}
            for name,start,end,sign in [('positive',2.3,2.9,1),('negative',5.3,5.9,-1),('zero',7.4,7.9,0)]:
                rows=[r for r in self.feedback if start<r['physics_ns']*1e-9-self.arm_time<end]
                if not rows:self.finish(False,'Missing native execution feedback');return
                values=np.array([r['applied_setpoint'] for r in rows]);rpm=np.array([r['rpm'] for r in rows]);force=np.array([r['thrust_N'] for r in rows])
                expected_rpm=sign*(-1 if item['inverted'] else 1)*0.12*item['max_rpm']
                expected_force=sign*native_sign*p['density_kg_m3']*item['diameter_m']**4*item['kt_forward']*(0.12*item['max_rpm']/60)**2
                good=(np.max(np.abs(np.delete(values,index,axis=1)))<1e-12 and
                      abs(float(values[:,index].mean())-sign*0.12)<1e-8 and
                      abs(float(rpm[:,index].mean())-expected_rpm)<max(15,abs(expected_rpm)*0.1) and
                      abs(float(force[:,index].mean())-expected_force)<max(0.05,abs(expected_force)*0.15))
                windows[name]=dict(pass_=bool(good),expected_rpm=expected_rpm,actual_rpm=float(rpm[:,index].mean()),
                                   expected_thrust_N=expected_force,actual_thrust_N=float(force[:,index].mean()),
                                   setpoint=float(values[:,index].mean()))
            passed=all(w['pass_'] for w in windows.values()) and self.terminal.get('state')=='DISARMED'
            self.finish(passed,'Native single-thruster positive/negative/zero diagnostic',channel=item['name'],windows=windows,fixed_fixture=True)

    def velocity_case(self,t):
        # Final case details and thresholds are loaded from the frozen acceptance manifest.
        spec=self.specification['cases'].get(self.case)
        if spec is None:self.finish(False,'Unknown case');return
        zero=float(spec.get('zero_sec',5));step=float(spec.get('step_sec',10));back=float(spec.get('return_sec',8))
        target=spec.get('target',[0.,0.,0.,0.]);recovery=float(spec.get('recovery_sec',0))
        return_start=zero+step+recovery
        self.target=list(target) if zero<=t<zero+step else list(spec['recovery_target']) if zero+step<=t<return_start else [0.]*4
        if t<return_start+back:self.request(self.target)
        elif not self.disarmed and not self.future:self.call('DISARM')
        if t>=return_start+back+2:
            rows=[s for s in self.states if self.arm_time<=s['wall']<self.arm_time+return_start+back]
            steady_start,steady_end=(return_start-4,return_start) if recovery else (zero+step-4,zero+step)
            assessed_target=spec.get('recovery_target',target)
            steady=[s for s in rows if steady_start<=s['wall']-self.arm_time<steady_end]
            returned=[s for s in rows if return_start+back-4<=s['wall']-self.arm_time<return_start+back]
            if not steady or not returned:self.finish(False,'Missing steady-state samples');return
            v=np.array([s['velocity'] for s in steady]);ang=np.array([s['rpy'] for s in steady]);rv=np.array([s['velocity'] for s in returned])
            rmse=np.sqrt(np.mean((v[:,[0,1,2,5]]-assessed_target)**2,axis=0));return_rms=np.sqrt(np.mean(rv[:,[0,1,2,5]]**2,axis=0))
            attitude=np.sqrt(np.mean(ang[:,:2]**2,axis=0))*180/math.pi
            limits=[max(0.02,abs(x)*0.2) if x else 0.03 for x in assessed_target[:3]]+[max(0.03,abs(assessed_target[3])*0.2)]
            passed=bool(self.outputs and np.all(rmse<=limits) and np.all(return_rms<=0.03) and np.all(attitude<=3) and self.terminal.get('state')=='DISARMED')
            additional={}
            if recovery:
                additional['saturation_observed']=any(o['saturated'] for o in self.outputs)
                passed=passed and additional['saturation_observed']
            if self.case=='yaw90_body_vx':
                d=np.array(rows[-1]['position'])-rows[0]['position']
                additional['world_direction_ok']=bool(d[1]>.7 and abs(d[0])<.25)
                passed=passed and additional['world_direction_ok']
            if self.case=='tilted_level':
                initial=np.degrees(self.states[0]['rpy'][:2])
                additional['initial_roll_pitch_deg']=initial.tolist()
                passed=passed and bool(np.all(np.abs(initial)>3.5))
            step_rows=[s for s in rows if zero<=s['wall']-self.arm_time<zero+step]
            peak=np.array([s['velocity'] for s in step_rows])[:,[0,1,2,5]]
            overshoot=[max(0.,float(np.max(peak[:,i]*np.sign(v)))-abs(v)) if v else float(np.max(np.abs(peak[:,i]))) for i,v in enumerate(target)]
            allv=np.array([s['velocity'] for s in rows]);alltarget=np.array([s['target'] for s in rows])
            self.finish(passed,'Body velocity and level-attitude finite case',steady_rmse=rmse.tolist(),assessed_target=assessed_target,thresholds=limits,
                return_rms=return_rms.tolist(),roll_pitch_rms_deg=attitude.tolist(),
                full_rmse=np.sqrt(np.mean((allv[:,[0,1,2,5]]-alltarget)**2,axis=0)).tolist(),
                transient_peak_velocity=np.max(np.abs(allv),axis=0).tolist(),
                displacement=(np.array(rows[-1]['position'])-rows[0]['position']).tolist(),
                saturation_ratio=float(np.mean([o['saturated'] for o in self.outputs])) if self.outputs else None,
                overshoot=overshoot,additional_checks=additional,
                request_to_controller_p99_sec=float(np.quantile([o['request_age_sec'] for o in self.outputs],.99)) if self.outputs else None,
                controller_period_p99_sec=float(np.quantile([p['period_sec'] for p in self.periods],.99)) if self.periods else None)

    def fault_case(self,t):
        # Inject only PIDs recorded by this run's launch. Physics remains alive.
        kind=self.case.removeprefix('fault_')
        if self.injected is None:
            self.request([0.15,0.,0.,0.]) if self.config['control_mode']=='body_velocity' else self.request([0.]*4,[0.12]+[0.]*7)
            if t>=4 and self.terminal and max(abs(x) for x in self.terminal['applied_setpoint'])>0.02:
                self.injected=time.monotonic_ns();self.event('injection',kind=kind,injection_ns=self.injected)
                processes={r['name']:r for r in map(json.loads,(self.folder/'process-starts.jsonl').read_text().splitlines())}
                target={'guard':'guard','controller':'controller','adapter':'actuator_adapter','state':'observation_adapter','rviz':'rviz'}.get(kind)
                if target:
                    (self.folder/'expected-exits.json').write_text(json.dumps([target]))
                    pid=processes[target]['pid']
                    if not Path(f'/proc/{pid}/cmdline').exists():self.finish(False,'Injection PID absent');return
                    start_ticks=int(Path(f'/proc/{pid}/stat').read_text().rsplit(') ',1)[1].split()[19])
                    if start_ticks!=processes[target]['proc_start_ticks']:self.finish(False,'Injection PID identity changed');return
                    os.kill(pid,signal.SIGKILL)
                elif kind in ('clock_pause','clock_rewind'):
                    secret=json.loads((self.folder/'session.json').read_text())['terminal_secret']
                    self.fixture.publish(String(data=json.dumps(dict(run=self.folder.name,secret=secret,sent_ns=time.monotonic_ns(),
                        op='hold_clock' if kind=='clock_pause' else 'rewind_clock'))))
                elif kind=='state_frozen':
                    secret=json.loads((self.folder/'session.json').read_text())['terminal_secret']
                    self.observation_fixture.publish(String(data=json.dumps(dict(run=self.folder.name,secret=secret,
                        sent_ns=time.monotonic_ns(),op='freeze_state'))))
                elif kind=='disarm':self.call('DISARM')
                elif kind=='latch':self.call('FAULT')
                self.extra['old_request']=copy.deepcopy(self.last_message)
                self.extra['old_native']=self.last_native
            elif t>10:self.finish(False,'No nonzero actual setpoint available for fault injection')
        else:
            since=(time.monotonic_ns()-self.injected)*1e-9
            if kind!='source' and kind not in ('disarm','latch'):self.request([0.15,0.,0.,0.]) if self.config['control_mode']=='body_velocity' else self.request([0.]*4,[0.12]+[0.]*7)
            if since>0.7 and not self.extra.get('restored') and kind in ('clock_pause','state_frozen'):
                secret=json.loads((self.folder/'session.json').read_text())['terminal_secret']
                message=String(data=json.dumps(dict(run=self.folder.name,secret=secret,sent_ns=time.monotonic_ns(),op='resume_clock' if kind=='clock_pause' else 'resume_state')))
                (self.fixture if kind=='clock_pause' else self.observation_fixture).publish(message)
                self.extra['restored']=True;self.event('fault_input_restored',kind=kind)
            if since>0.7 and kind!='rviz':
                # Exact old token/generation/sequence/stamp replay cannot renew authority.
                self.publisher.publish(self.extra['old_request'])
                if kind=='adapter' and self.extra.get('old_native'):
                    if self.native_replay is None:self.native_replay=self.create_publisher(String,'sim/terminal/input',1)
                    self.native_replay.publish(String(data=self.extra['old_native']));self.replay_count+=1
            if since>=2.5:
                after=[f for f in self.feedback if f['wall_ns']>=self.injected]
                zero=next((f for f in after if max(abs(x) for x in f['applied_setpoint'])<1e-12),None)
                if kind=='rviz':
                    passed=self.guard.get('state')=='ARMED' and self.terminal.get('state')=='ARMED' and self.clock-self.first_clock>0
                    self.call('DISARM');self.finish(passed,'UI SIGKILL does not stop core control',injection_ns=self.injected);return
                latency=None if zero is None else (zero['applied_ns']-self.injected)*1e-9
                expected='DISARMED' if kind=='disarm' else 'FAULT'
                reset_ok=(kind=='controller' or self.config['control_mode']=='actuator_probe' or bool(self.periods and not any(self.periods[-1]['integral']) and not any(self.periods[-1]['attitude_integral'])))
                passed=reset_ok and latency is not None and 0<=latency<=0.5 and self.terminal.get('state')==expected and bool(after and after[-1]['physics_ns']>self.injected+2_000_000_000)
                self.finish(passed,'Terminal neutralization after real fault injection',injection_ns=self.injected,
                    neutralization_latency_sec=latency,controller_integral_reset=reset_ok,terminal_fault_ns=self.terminal.get('fault_ns'),
                    terminal_replay_messages=self.replay_count,receiver_neutral_ns=self.terminal.get('neutral_ns'),actual_applied_ns=zero['applied_ns'] if zero else None,
                    actual_rpm_at_end=self.terminal.get('rpm'),actual_thrust_at_end=self.terminal.get('thrust_N'),
                    physics_continued=bool(after and after[-1]['physics_ns']>self.injected+2_000_000_000))


def main(args=None):
    rclpy.init(args=args,signal_handler_options=SignalHandlerOptions.NO);node=Case()
    stop=[False]
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stop.__setitem__(0,True))
    try:
        while rclpy.ok() and not stop[0] and not node.done:rclpy.spin_once(node,timeout_sec=0.1)
        code=getattr(node,'result',1)
    except (KeyboardInterrupt,rclpy.executors.ExternalShutdownException):code=1
    finally:node.stream.close();node.destroy_node();rclpy.try_shutdown()
    raise SystemExit(code)
