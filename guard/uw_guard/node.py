"""Simulation-only exclusive authority; explicit ARM and latched failure."""
import copy,json,math,time,uuid
from pathlib import Path
import yaml
import signal
import rclpy
from rclpy.signals import SignalHandlerOptions
from rclpy.node import Node
from rclpy.clock import Clock,ClockType
from std_msgs.msg import String
from nav_msgs.msg import Odometry
from rosgraph_msgs.msg import Clock as ClockMsg
from uw_interfaces.msg import ControlRequest,AuthorizedCommand,ActuatorOutput
from uw_interfaces.srv import Control
from uw_guard.contracts import validate_request
from uw_robot.thrusters import Allocation,load_profile


def ns(stamp):return stamp.sec*1_000_000_000+stamp.nanosec


class Guard(Node):
    def __init__(self):
        super().__init__('control_guard')
        self.run_dir=Path(self.declare_parameter('run_dir','').value)
        self.config=yaml.safe_load((self.run_dir/'resolved_config.yaml').read_text())
        self.state_prefix=self.declare_parameter('state_frame_prefix',self.config['namespace']).value
        survey=(self.config.get('survey_profile')=='known_route_capture_v1' and self.config.get('control_state_source')=='ground_truth_debug' and self.config.get('scene_profile')=='porth_sump9')
        self.estimated_control=self.config.get('schema_version')==4 and not survey
        self.write_control_status=self.estimated_control or survey
        self.estimated_horizontal_limit=self.declare_parameter('estimated_horizontal_limit_m',1.5).value
        self.estimated_vertical_limit=self.declare_parameter('estimated_vertical_limit_m',.6).value
        if not (0<self.estimated_horizontal_limit<=4 and 0<self.estimated_vertical_limit<=1):raise ValueError('Invalid estimated envelope')
        self.last_status_write=0;self.estimator={};self.estimator_wall=0;self.state_origin=None;self.epoch=None
        self.run=self.run_dir.name;self.secret=json.loads((self.run_dir/'session.json').read_text())['terminal_secret']
        self.frame=self.config['namespace']+'/base_link';self.mode=self.config['control_mode']
        self.profile=load_profile(self.run_dir/'thrusters.yaml');self.names=[t['name'] for t in self.profile['thrusters']]
        self.defaults=yaml.safe_load((self.run_dir/'guard-parameters.yaml').read_text())
        if self.estimated_control:self.defaults['sources'].append('navigation')
        for key,value in {'request_timeout_sec':.25,'state_timeout_sec':.25,'clock_timeout_sec':.25,'future_tolerance_sec':.05,'ros_age_limit_sec':.25,'probe_limit':.15}.items():
            if self.defaults[key]!=value:raise ValueError('Safety budget requires a protocol revision: '+key)
        self.state='DISARMED';self.reason='startup';self.generation=0;self.token='';self.source='benchmark'
        self.clock_ns=None;self.clock_wall=0;self.state_stamp=0;self.state_wall=0;self.state_valid=False;self.envelope_valid=False
        self.terminal={};self.terminal_wall=0;self.mapping=False;self.arm_wall=0
        self.ready_since=None;self.ready_for_arm=False
        self.last_sequence=0;self.last_request=None;self.deadline=0;self.gate_sequence=0;self.rejects=0;self.last_reject=''
        self.gate=self.create_publisher(String,'sim/terminal/gate',1)
        self.approved=self.create_publisher(AuthorizedCommand,'control/approved',1)
        self.status=self.create_publisher(String,'control/status',1)
        self.output=self.create_publisher(ActuatorOutput,'control/output',1) if self.mode=='actuator_probe' else None
        self.create_subscription(ClockMsg,'/clock',self.on_clock,1)
        self.create_subscription(Odometry,'state/odometry',self.on_state,1)
        if self.estimated_control:self.create_subscription(String,'localization/status',self.on_estimator,1)
        self.create_subscription(String,'sim/terminal/status',self.on_terminal,1)
        self.create_subscription(ControlRequest,'control/request',self.on_request,1)
        self.create_service(Control,'control/authority',self.service)
        self.create_timer(0.02,self.tick,clock=Clock(clock_type=ClockType.STEADY_TIME))

    def gate_message(self,op,reason=''):
        self.gate_sequence+=1
        p=dict(op=op,run=self.run,secret=self.secret,generation=self.generation,token=self.token,
               gate_seq=self.gate_sequence,sent_ns=time.monotonic_ns(),reason=reason)
        self.gate.publish(String(data=json.dumps(p)))

    def fault(self,reason):
        if self.state!='ARMED':return
        self.state='FAULT';self.reason=reason;self.last_request=None;self.token=''
        self.gate_message('FAULT',reason)

    def on_clock(self,msg):
        value=ns(msg.clock)
        if self.clock_ns is not None and value<self.clock_ns:self.fault('clock_rewind')
        if value!=self.clock_ns:self.clock_wall=time.monotonic_ns()
        self.clock_ns=value

    def on_state(self,msg):
        stamp=ns(msg.header.stamp);q=msg.pose.pose.orientation;v=msg.twist.twist
        p=msg.pose.pose.position
        values=[q.x,q.y,q.z,q.w,p.x,p.y,p.z,v.linear.x,v.linear.y,v.linear.z,v.angular.x,v.angular.y,v.angular.z]
        self.state_valid=(msg.header.frame_id==self.state_prefix+'/odom' and msg.child_frame_id==self.state_prefix+'/base_link' and
            all(math.isfinite(x) for x in values) and abs(sum(x*x for x in values[:4])-1)<1e-4)
        roll=math.atan2(2*(q.w*q.x+q.y*q.z),1-2*(q.x*q.x+q.y*q.y))
        pitch=math.asin(max(-1,min(1,2*(q.w*q.y-q.z*q.x))))
        e=self.defaults['safety_envelope']
        self.envelope_valid=(e['depth_enu_m'][0]<p.z<e['depth_enu_m'][1] and
            max(abs(p.x),abs(p.y))<e['horizontal_position_abs_m'] and
            max(abs(roll),abs(pitch))<math.radians(e['roll_pitch_peak_deg']) and
            max(abs(v.linear.x),abs(v.linear.y),abs(v.linear.z))<e['linear_speed_peak_m_s'] and
            max(abs(v.angular.x),abs(v.angular.y),abs(v.angular.z))<e['angular_speed_peak_rad_s'])
        if self.estimated_control:
            if self.state_origin is None and self.state_valid:self.state_origin=[p.x,p.y,p.z]
            origin=self.state_origin or [0,0,0]
            self.envelope_valid=(max(abs(p.x-origin[0]),abs(p.y-origin[1]))<self.estimated_horizontal_limit and abs(p.z-origin[2])<self.estimated_vertical_limit and
                max(abs(roll),abs(pitch))<math.radians(25) and
                max(abs(v.linear.x),abs(v.linear.y),abs(v.linear.z))<.6 and
                max(abs(v.angular.x),abs(v.angular.y),abs(v.angular.z))<.6)
            cov=list(msg.pose.covariance)+list(msg.twist.covariance)
            self.state_valid=self.state_valid and all(math.isfinite(x) for x in cov) and all(0<=msg.pose.covariance[i]<=.25 for i in (0,7,14))
        if stamp<self.state_stamp:self.fault('state_time_rewind')
        if stamp>self.state_stamp:self.state_wall=time.monotonic_ns()
        self.state_stamp=stamp
        if not self.state_valid:self.fault('invalid_state')

    def on_estimator(self,msg):
        try:
            report=json.loads(msg.data)
            if report.get('run')!=self.run:self.fault('estimator_run');return
            if self.epoch is not None and report.get('epoch')!=self.epoch:self.fault('estimator_epoch_changed')
            self.epoch=report.get('epoch');self.estimator=report;self.estimator_wall=time.monotonic_ns()
            if report.get('state') not in ('READY_STATIC','TRACKING'):self.fault('estimator_'+str(report.get('state')))
        except (ValueError,TypeError):self.fault('estimator_invalid')

    def on_terminal(self,msg):
        try:
            self.terminal=json.loads(msg.data);self.terminal_wall=time.monotonic_ns()
            if self.terminal['run']!=self.run:self.fault('terminal_run_mismatch');return
            if not self.mapping:
                allocation=Allocation(self.profile,self.terminal['model']);self.mapping=True
                (self.run_dir/'allocation-model.json').write_text(json.dumps(dict(model=self.terminal['model'],
                    matrix=allocation.matrix.tolist(),singular_values=allocation.singular_values.tolist(),
                    condition_number=float(allocation.singular_values[0]/allocation.singular_values[-1])),indent=2))
            if self.terminal['state']=='FAULT':self.fault('terminal:'+self.terminal['reason'])
        except (ValueError,KeyError,TypeError):self.mapping=False;self.fault('mapping_invalid')

    def health(self):
        now=time.monotonic_ns()
        if self.config['mode']!='simulation_research':return 'not_simulation'
        if self.estimated_control:
            if now-self.estimator_wall>250_000_000:return 'estimator_health_stale'
            if self.estimator.get('state') not in ('READY_STATIC','TRACKING'):return 'estimator_not_ready'
            if self.clock_ns is not None and any(self.clock_ns-int(self.estimator.get(k,0)*1e9)>250_000_000 for k in ('image_stamp','imu_stamp')):return 'estimator_sensor_stale'
            if self.count_publishers('state/odometry')!=1 or self.count_publishers('localization/status')!=1:return 'estimator_authority'
        if not self.mapping:return 'mapping_not_verified'
        if not self.state_valid or now-self.state_wall>250_000_000:return 'state_stale'
        if not self.envelope_valid:return 'safety_envelope'
        if self.clock_ns is None or now-self.clock_wall>250_000_000:return 'clock_stale'
        if abs(self.clock_ns-self.state_stamp)>250_000_000:return 'state_clock_mismatch'
        if now-self.terminal_wall>200_000_000:return 'terminal_stale'
        if self.count_publishers('/clock')!=1:return 'clock_authority'
        for topic in ('control/approved','control/output','sim/terminal/gate','sim/terminal/input'):
            if self.count_publishers(topic)!=1:return 'authority:'+topic
        return None

    def service(self,req,res):
        error=None
        if req.run_id!=self.run:error='wrong_run'
        elif req.action=='STATUS':pass
        elif req.action=='DISARM':
            if self.state!='FAULT':self.state='DISARMED';self.reason='explicit_disarm'
            self.token='';self.last_request=None;self.gate_message('DISARM')
        elif req.action=='CLEAR_FAULT':
            error=self.health()
            if not error:
                self.state='DISARMED';self.reason='explicit_reset';self.token='';self.last_request=None;self.gate_message('RESET')
        elif req.action=='SELECT_SOURCE':
            if req.source not in self.defaults['sources']:error='unknown_source'
            else:
                if self.state!='FAULT':self.state='DISARMED'
                self.source=req.source;self.token='';self.last_request=None;self.gate_message('DISARM')
        elif req.action=='ARM':
            error=self.health()
            if not error and not self.ready_for_arm:error='readiness_stabilizing'
            if not error and self.state!='DISARMED':error='explicit_disarm_or_reset_required'
            if not error and self.terminal.get('state')!='DISARMED':error='terminal_not_disarmed'
            if not error and req.source not in self.defaults['sources']:error='unknown_source'
            if not error:
                self.generation+=1;self.token=uuid.uuid4().hex;self.source=req.source;self.state='ARMED'
                self.reason='explicit_arm';self.arm_wall=time.monotonic_ns();self.deadline=self.arm_wall+200_000_000
                self.last_sequence=0;self.last_request=None;self.gate_message('ARM')
        elif req.action=='FAULT':
            self.fault('explicit_fault')
        else:error='unknown_action'
        res.accepted=not error;res.reason=error or self.reason;res.state=self.state
        res.generation=self.generation;res.token=self.token;res.source=self.source
        return res

    def on_request(self,msg):
        error='not_armed' if self.state!='ARMED' else None
        v=msg.command.twist
        record=dict(run_id=msg.run_id,source=msg.source,token=msg.token,generation=msg.generation,
            sequence=msg.sequence,issued_ns=msg.issued_steady_ns,valid_until_ns=msg.valid_until_steady_ns,stamp_ns=ns(msg.command.header.stamp),
            frame=msg.command.header.frame_id,expected_frame=self.frame,
            twist=[v.linear.x,v.linear.y,v.linear.z,v.angular.x,v.angular.y,v.angular.z],
            names=list(msg.actuator_probe.name),setpoint=list(msg.actuator_probe.position))
        if not error:error=validate_request(record,time.monotonic_ns(),self.clock_ns,self.run,self.source,self.token,
            self.generation,self.last_sequence,self.mode,self.names,self.defaults['velocity_limits'])
        if error:
            self.rejects+=1;self.last_reject=error;return
        deadline=min(msg.issued_steady_ns+250_000_000,msg.valid_until_steady_ns or msg.issued_steady_ns+250_000_000)
        approved=AuthorizedCommand(request=msg,deadline_steady_ns=deadline)
        self.last_sequence=msg.sequence;self.last_request=approved;self.deadline=approved.deadline_steady_ns
        self.approved.publish(approved)
        if self.output:
            output=ActuatorOutput(authorization=approved,names=self.names,setpoint=list(msg.actuator_probe.position),
                                  computed_steady_ns=time.monotonic_ns())
            self.output.publish(output)

    def tick(self):
        healthy=self.health() is None
        if not healthy:self.ready_since=None
        elif self.ready_since is None:self.ready_since=time.monotonic()
        self.ready_for_arm=healthy and time.monotonic()-self.ready_since>=1.0
        if self.state=='ARMED':
            error=self.health()
            if not error and time.monotonic_ns()>self.deadline:error='original_request_expired'
            if error:self.fault(error)
            else:self.gate_message('LEASE')
        report=dict(run=self.run,state=self.state,reason=self.reason,source=self.source,generation=self.generation,
            state_source='OPENVINS_STEREO_IMU' if self.estimated_control else 'PRIVILEGED_DEBUG',epoch=self.epoch,
            ready=self.ready_for_arm,health=self.health(),rejected=self.rejects,last_reject=self.last_reject,
            request_seq=self.last_sequence,wall_ns=time.monotonic_ns(),deadline_ns=self.deadline)
        self.status.publish(String(data=json.dumps(report)))
        if self.write_control_status and time.monotonic_ns()-self.last_status_write>100_000_000:
            temporary=self.run_dir/'control-status.json.tmp';temporary.write_text(json.dumps(report));temporary.replace(self.run_dir/'control-status.json')
            self.last_status_write=time.monotonic_ns()


def main(args=None):
    rclpy.init(args=args,signal_handler_options=SignalHandlerOptions.NO);node=Guard()
    stop=[False]
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stop.__setitem__(0,True))
    try:
        while rclpy.ok() and not stop[0]:rclpy.spin_once(node,timeout_sec=.1)
    except (KeyboardInterrupt,rclpy.executors.ExternalShutdownException):pass
    finally:node.destroy_node();rclpy.try_shutdown()
