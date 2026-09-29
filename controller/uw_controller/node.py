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
from std_msgs.msg import String
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
        self.state_valid=False
        self.profile=load_profile(self.folder/'thrusters.yaml')
        self.control=None;self.command=None;self.state=None;self.state_wall=0;self.last_stamp=None;self.generation=None
        self.terminal={};self.guard={};self.last_tick=None
        self.output=self.create_publisher(ActuatorOutput,'control/output',1)
        self.status=self.create_publisher(String,'control/controller_status',1)
        self.create_subscription(AuthorizedCommand,'control/approved',lambda m:setattr(self,'command',m),1)
        self.create_subscription(Odometry,'state/odometry',self.on_state,1)
        self.create_subscription(String,'control/status',lambda m:setattr(self,'guard',json.loads(m.data)),1)
        self.create_subscription(String,'sim/terminal/status',self.on_terminal,1)
        self.create_timer(1/self.p['rate_hz'],self.tick,clock=Clock(clock_type=ClockType.STEADY_TIME))

    def on_state(self,msg):
        p=msg.pose.pose.position;q=msg.pose.pose.orientation;v=msg.twist.twist
        values=[p.x,p.y,p.z,q.x,q.y,q.z,q.w,v.linear.x,v.linear.y,v.linear.z,v.angular.x,v.angular.y,v.angular.z]
        self.state_valid=(all(math.isfinite(x) for x in values) and abs(q.x*q.x+q.y*q.y+q.z*q.z+q.w*q.w-1)<1e-4 and
            msg.header.frame_id==self.state_prefix+'/odom' and msg.child_frame_id==self.state_prefix+'/base_link')
        stamp=msg.header.stamp.sec+msg.header.stamp.nanosec*1e-9
        if self.state is None or stamp!=self.stamp:self.state_wall=time.monotonic_ns()
        self.state=msg;self.stamp=stamp

    def on_terminal(self,msg):
        self.terminal=json.loads(msg.data)
        if self.control is None:
            self.control=BodyController(self.p,Allocation(self.profile,self.terminal['model']))

    def reset(self):
        if self.control:self.control.reset()
        self.last_stamp=None;self.generation=None

    def tick(self):
        now=time.monotonic_ns();period=(now-self.last_tick)*1e-9 if self.last_tick else 0;self.last_tick=now
        active=(self.control and self.command and self.state and self.state_valid and self.guard.get('state')=='ARMED' and
                self.terminal.get('state')=='ARMED' and self.command.request.run_id==self.folder.name and
                self.command.request.generation==int(self.terminal.get('generation',0)) and
                now<self.command.deadline_steady_ns and now-self.state_wall<250_000_000)
        if not active:
            self.reset()
            self.status.publish(String(data=json.dumps(dict(wall_ns=now,state='IDLE',dt=0.,period_sec=period,
                generation=0,integral=[0.]*4,attitude_integral=[0.]*2,request_age_sec=0.))))
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
        output=ActuatorOutput(authorization=self.command,names=self.control.allocation.names,
                              setpoint=command.tolist(),saturated=saturated,computed_steady_ns=now)
        for wrench,values in ((output.requested_wrench,requested),(output.predicted_wrench,predicted)):
            wrench.force.x,wrench.force.y,wrench.force.z=map(float,values[:3])
            wrench.torque.x,wrench.torque.y,wrench.torque.z=map(float,values[3:])
        self.output.publish(output)
        self.status.publish(String(data=json.dumps(dict(wall_ns=now,dt=dt,period_sec=period,
            generation=gen,integral=self.control.integral.tolist(),attitude_integral=self.control.attitude_integral.tolist(),
            request_age_sec=(now-self.command.request.issued_steady_ns)*1e-9))))


def main(args=None):
    rclpy.init(args=args,signal_handler_options=SignalHandlerOptions.NO);node=Controller()
    stop=[False]
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stop.__setitem__(0,True))
    try:
        while rclpy.ok() and not stop[0]:rclpy.spin_once(node,timeout_sec=.1)
    except (KeyboardInterrupt,rclpy.executors.ExternalShutdownException):pass
    finally:node.destroy_node();rclpy.try_shutdown()
