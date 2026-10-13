"""50 Hz controller; monotonic expiry and validated simulation integration time."""
import json,time,math
from pathlib import Path
import yaml
import signal
import rclpy
from rclpy.signals import SignalHandlerOptions
from rclpy.node import Node
from rclpy.clock import Clock,ClockType
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Imu,FluidPressure
from std_msgs.msg import String
from rclpy.qos import qos_profile_sensor_data
from uw_interfaces.msg import AuthorizedCommand,ActuatorOutput
from uw_robot.thrusters import Allocation,load_profile
from uw_controller.core import BodyController,rpy


class Controller(Node):
    def __init__(self):
        super().__init__('body_velocity_controller')
        self.folder=Path(self.declare_parameter('run_dir','').value)
        self.p=yaml.safe_load((self.folder/'controller-parameters.yaml').read_text())
        self.config=yaml.safe_load((self.folder/'resolved_config.yaml').read_text())
        self.state_prefix=self.declare_parameter('state_frame_prefix',self.config['namespace']).value
        self.backend=self.declare_parameter('controller_backend',self.p.get('backend','body_pi')).value
        if self.backend not in ('body_pi','jepa_mppi'):raise ValueError('Unknown controller backend')
        self.estimator={};self.estimator_wall=0;self.feedback_valid=False
        if self.backend=='jepa_mppi':
            from ament_index_python.packages import get_package_share_directory
            from uw_controller.checkpoint import validate_feedback
            validate_feedback(self.config,self.state_prefix)
            if self.resolve_topic_name('state/odometry')!='/'+self.config['namespace']+'/state/odometry':
                raise ValueError('JEPA-MPPI state topic cannot be remapped')
            settings_path=self.declare_parameter('jepa_settings_path',str(Path(get_package_share_directory('uw_controller'))/'config/jepa_mppi.yaml')).value
            self.jepa_settings=yaml.safe_load(Path(settings_path).read_text())
            checkpoint=Path(self.jepa_settings['checkpoint']).expanduser()
            if not checkpoint.is_absolute():checkpoint=Path(get_package_share_directory('uw_controller'))/checkpoint
            self.jepa_settings['checkpoint']=str(checkpoint.resolve())
        self.state_valid=False
        self.profile=load_profile(self.folder/'thrusters.yaml')
        self.control=None;self.command=None;self.state=None;self.state_wall=0;self.last_stamp=None;self.generation=None
        self.terminal={};self.guard={};self.last_tick=None
        self.output=self.create_publisher(ActuatorOutput,'control/output',1)
        self.status=self.create_publisher(String,'control/controller_status',1)
        self.create_subscription(AuthorizedCommand,'control/approved',lambda m:setattr(self,'command',m),1)
        self.create_subscription(Odometry,'state/odometry',self.on_state,1)
        if self.backend=='jepa_mppi':
            self.create_subscription(Imu,'sensors/imu',self.on_imu,qos_profile_sensor_data)
            self.create_subscription(FluidPressure,'sensors/pressure',self.on_pressure,qos_profile_sensor_data)
            self.create_subscription(String,'localization/status',self.on_estimator,1)
        self.create_subscription(String,'control/status',lambda m:setattr(self,'guard',json.loads(m.data)),1)
        self.create_subscription(String,'sim/terminal/status',self.on_terminal,1)
        self.create_timer(1/self.p['rate_hz'],self.tick,clock=Clock(clock_type=ClockType.STEADY_TIME))

    def on_state(self,msg):
        p=msg.pose.pose.position;q=msg.pose.pose.orientation;v=msg.twist.twist
        values=[p.x,p.y,p.z,q.x,q.y,q.z,q.w,v.linear.x,v.linear.y,v.linear.z,v.angular.x,v.angular.y,v.angular.z]
        self.state_valid=(all(math.isfinite(x) for x in values) and abs(q.x*q.x+q.y*q.y+q.z*q.z+q.w*q.w-1)<1e-4 and
            msg.header.frame_id==self.state_prefix+'/odom' and msg.child_frame_id==self.state_prefix+'/base_link')
        if self.backend=='jepa_mppi':
            covariance=list(msg.pose.covariance)+list(msg.twist.covariance)
            self.state_valid=self.state_valid and all(math.isfinite(x) for x in covariance) and all(0<=msg.pose.covariance[i]<=.25 for i in (0,7))
        stamp=msg.header.stamp.sec+msg.header.stamp.nanosec*1e-9
        if self.state is None or stamp!=self.stamp:self.state_wall=time.monotonic_ns()
        self.state=msg;self.stamp=stamp
        if self.backend=='jepa_mppi' and self.control:
            self.feedback_valid=self.state_valid and self.control.observe(stamp,values[:3],values[3:7],values[7:])

    def on_imu(self,msg):
        if not self.control:return
        a=msg.linear_acceleration;g=msg.angular_velocity
        if msg.header.frame_id!=self.config['namespace']+'/imu_link' or msg.orientation_covariance[0]!=-1:return
        stamp=msg.header.stamp.sec+msg.header.stamp.nanosec*1e-9
        if not self.control.on_imu(stamp,[a.x,a.y,a.z],[g.x,g.y,g.z]):
            if not all(math.isfinite(x) for x in (a.x,a.y,a.z,g.x,g.y,g.z)):self.control.imu.samples.clear();self.control.clear_history()

    def on_pressure(self,msg):
        if not self.control:return
        if msg.header.frame_id!=self.config['namespace']+'/pressure':return
        stamp=msg.header.stamp.sec+msg.header.stamp.nanosec*1e-9
        try:self.control.on_pressure(stamp,msg.fluid_pressure)
        except ValueError:self.control.pressure.samples.clear();self.control.clear_history();self.feedback_valid=False

    def on_estimator(self,msg):
        try:
            report=json.loads(msg.data)
            if not isinstance(report,dict):raise ValueError('Invalid estimator report')
        except ValueError:self.estimator={};self.feedback_valid=False;return
        if self.control and self.estimator and report.get('epoch')!=self.estimator.get('epoch'):self.control.clear_history()
        self.estimator=report;self.estimator_wall=time.monotonic_ns()

    def estimated_feedback_healthy(self,now):
        return (self.feedback_valid and self.control.inputs_ready(self.stamp,now) and
            now-self.estimator_wall<250_000_000 and self.estimator.get('run')==self.folder.name and
            self.estimator.get('source')=='OPENVINS_STEREO_IMU' and self.estimator.get('state') in ('READY_STATIC','TRACKING') and
            self.guard.get('state_source')=='OPENVINS_STEREO_IMU')

    def on_terminal(self,msg):
        self.terminal=json.loads(msg.data)
        if self.control is None:
            allocation=Allocation(self.profile,self.terminal['model'])
            if self.backend=='jepa_mppi':
                from uw_controller.checkpoint import CheckpointController
                reference=allocation
                if self.profile.get('variant')!='bluerov2_six_disaware':
                    from ament_index_python.packages import get_package_share_directory
                    profile=load_profile(Path(get_package_share_directory('uw_robot'))/'config/thrusters_six_disaware.yaml')
                    model=dict(names=[t['name'] for t in profile['thrusters']],cg_frd_m=self.terminal['model']['cg_frd_m'],
                        geometry=[dict(position_frd=t['position_frd'],axis_frd=t['axis_frd']) for t in profile['thrusters']])
                    reference=Allocation(profile,model)
                self.control=CheckpointController(self.p,allocation,self.jepa_settings,reference)
            else:self.control=BodyController(self.p,allocation)
        if self.backend=='jepa_mppi' and self.terminal.get('run')==self.folder.name and self.terminal.get('names')==self.control.allocation.names:
            self.control.on_applied(int(self.terminal['clock_ns'])*1e-9,self.terminal['applied_setpoint'])

    def reset(self):
        if self.control:self.control.reset()
        self.last_stamp=None;self.generation=None

    def tick(self):
        now=time.monotonic_ns();period=(now-self.last_tick)*1e-9 if self.last_tick else 0;self.last_tick=now
        active=(self.control and self.command and self.state and self.state_valid and self.guard.get('state')=='ARMED' and
                self.terminal.get('state')=='ARMED' and self.command.request.run_id==self.folder.name and
                self.command.request.generation==int(self.terminal.get('generation',0)) and
                now<self.command.deadline_steady_ns and now-self.state_wall<250_000_000)
        if active and self.backend=='jepa_mppi':active=self.estimated_feedback_healthy(now)
        if not active:
            self.reset()
            self.status.publish(String(data=json.dumps(dict(wall_ns=now,state='IDLE',dt=0.,period_sec=period,
                generation=0,integral=[0.]*4,attitude_integral=[0.]*2,request_age_sec=0.,backend=self.backend,
                **(self.control.report() if self.backend=='jepa_mppi' and self.control else {})))))
            return
        gen=self.command.request.generation
        if gen!=self.generation:self.reset();self.generation=gen
        if self.last_stamp is None:self.last_stamp=self.stamp;return
        dt=self.stamp-self.last_stamp
        if dt==0:return
        self.last_stamp=self.stamp
        v=self.state.twist.twist;q=self.state.pose.pose.orientation;t=self.command.request.command.twist
        velocity=[v.linear.x,v.linear.y,v.linear.z,v.angular.x,v.angular.y,v.angular.z]
        angles=rpy([q.x,q.y,q.z,q.w]);target=[t.linear.x,t.linear.y,t.linear.z,t.angular.z]
        try:command,requested,predicted,saturated=self.control.update(target,velocity,angles,dt)
        except ValueError:self.reset();return
        now=time.monotonic_ns()
        if now>=self.command.deadline_steady_ns or now-self.state_wall>=250_000_000:self.reset();return
        if self.backend=='jepa_mppi' and not self.estimated_feedback_healthy(now):self.reset();return
        output=ActuatorOutput(authorization=self.command,names=self.control.allocation.names,
                              setpoint=command.tolist(),saturated=saturated,computed_steady_ns=now)
        for wrench,values in ((output.requested_wrench,requested),(output.predicted_wrench,predicted)):
            wrench.force.x,wrench.force.y,wrench.force.z=map(float,values[:3])
            wrench.torque.x,wrench.torque.y,wrench.torque.z=map(float,values[3:])
        self.output.publish(output)
        self.status.publish(String(data=json.dumps(dict(wall_ns=now,dt=dt,period_sec=period,
            generation=gen,integral=self.control.integral.tolist(),attitude_integral=self.control.attitude_integral.tolist(),
            request_age_sec=(now-self.command.request.issued_steady_ns)*1e-9,backend=self.backend,
            **(self.control.report() if self.backend=='jepa_mppi' else {})))))


def main(args=None):
    rclpy.init(args=args,signal_handler_options=SignalHandlerOptions.NO);node=Controller()
    stop=[False]
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stop.__setitem__(0,True))
    try:
        while rclpy.ok() and not stop[0]:rclpy.spin_once(node,timeout_sec=.1)
    except (KeyboardInterrupt,rclpy.executors.ExternalShutdownException):pass
    finally:
        if node.backend=='jepa_mppi' and node.control:node.control.close()
        node.destroy_node();rclpy.try_shutdown()
