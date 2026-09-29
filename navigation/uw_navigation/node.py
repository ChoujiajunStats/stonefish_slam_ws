"""20 Hz estimated-state tracker. Task intent expires even while this process lives."""
import json,math,signal,time
from pathlib import Path
import yaml
import rclpy
from rclpy.node import Node
from rclpy.clock import Clock,ClockType
from rclpy.signals import SignalHandlerOptions
from nav_msgs.msg import Odometry
from std_msgs.msg import String
from uw_interfaces.msg import NavigationGoal,ControlRequest
from uw_navigation.core import guide,yaw


class Tracker(Node):
    def __init__(self):
        super().__init__('navigation')
        self.out=Path(self.declare_parameter('run_dir','').value);self.cfg=yaml.safe_load((self.out/'resolved_config.yaml').read_text());self.ns=self.cfg['namespace']
        self.p=yaml.safe_load((self.out/'navigation-parameters.yaml').read_text())
        self.goal=None;self.state=None;self.state_wall=0;self.guard={};self.guard_wall=0;self.last_stamp=0
        self.sequence=0;self.goal_sequence=0;self.identity=None;self.dwell=None
        self.pub=self.create_publisher(ControlRequest,'control/request',1);self.status=self.create_publisher(String,'navigation/status',1)
        self.create_subscription(NavigationGoal,'navigation/goal',self.on_goal,1)
        self.create_subscription(Odometry,'state/odometry',self.on_state,1)
        self.create_subscription(String,'control/status',self.on_guard,1)
        self.create_timer(1/self.p['rate_hz'],self.tick,clock=Clock(clock_type=ClockType.STEADY_TIME))
    def on_guard(self,m):self.guard=json.loads(m.data);self.guard_wall=time.monotonic_ns()
    def on_state(self,m):
        stamp=m.header.stamp.sec*10**9+m.header.stamp.nanosec
        if stamp>self.last_stamp:self.state_wall=time.monotonic_ns()
        elif stamp<self.last_stamp:self.goal=None;self.dwell=None
        self.last_stamp=stamp;self.state=m
    def on_goal(self,m):
        now=time.monotonic_ns();identity=(m.mission_id,m.generation,m.token)
        if m.run_id!=self.out.name or m.target.header.frame_id!=self.ns+'/odom':return
        if not 0<=now-m.issued_steady_ns<250_000_000 or now>=m.deadline_steady_ns:return
        if self.guard.get('source')!='navigation' or self.guard.get('generation')!=m.generation or self.guard.get('epoch')!=m.epoch:return
        if identity!=self.identity:self.identity=identity;self.goal_sequence=0;self.sequence=0;self.dwell=None
        if m.sequence<=self.goal_sequence:return
        if self.goal is None or self.goal.waypoint_index!=m.waypoint_index:self.dwell=None
        self.goal_sequence=m.sequence;self.goal=m
    def tick(self):
        now=time.monotonic_ns();g=self.goal;s=self.state
        healthy=(g is not None and s is not None and self.guard.get('state')=='ARMED' and self.guard.get('source')=='navigation' and
            self.guard.get('generation')==g.generation and now-self.guard_wall<250_000_000 and now-self.state_wall<250_000_000 and
            0<=now-g.issued_steady_ns<250_000_000 and now<g.deadline_steady_ns and
            s.header.frame_id==self.ns+'/odom' and s.child_frame_id==self.ns+'/base_link')
        report=dict(run=self.out.name,wall_ns=now,state='IDLE',reached=False)
        if healthy:
            p=s.pose.pose.position;q=s.pose.pose.orientation;t=g.target.pose.position;r=g.target.pose.orientation;v=s.twist.twist
            try:
                command,distance,angle=guide([p.x,p.y,p.z],[q.x,q.y,q.z,q.w],[t.x,t.y,t.z],yaw([r.x,r.y,r.z,r.w]),self.p)
                settled=(distance<self.p['position_tolerance_m'] and abs(angle)<self.p['yaw_tolerance_rad'] and
                    math.sqrt(v.linear.x**2+v.linear.y**2+v.linear.z**2)<self.p['settle_speed_m_s'] and abs(v.angular.z)<self.p['settle_yaw_rate_rad_s'])
                self.dwell=(self.dwell or now) if settled else None
                self.sequence+=1
                m=ControlRequest(run_id=g.run_id,source='navigation',token=g.token,generation=g.generation,sequence=self.sequence,
                    issued_steady_ns=g.issued_steady_ns,valid_until_steady_ns=g.deadline_steady_ns)
                # Preserve the task lease. Do not turn a stale task into a new intent.
                m.command.header.stamp=s.header.stamp;m.command.header.frame_id=self.ns+'/base_link'
                m.command.twist.linear.x,m.command.twist.linear.y,m.command.twist.linear.z,m.command.twist.angular.z=command
                self.pub.publish(m)
                report.update(state='TRACKING',mission_id=g.mission_id,generation=g.generation,waypoint_index=g.waypoint_index,
                    distance_m=distance,yaw_error_rad=angle,target_velocity=command,reached=self.dwell is not None and (now-self.dwell)*1e-9>=self.p['dwell_sec'])
            except (ValueError,OverflowError):self.goal=None;self.dwell=None;report['state']='INVALID_STATE'
        else:self.dwell=None
        self.status.publish(String(data=json.dumps(report)))


def main(args=None):
    rclpy.init(args=args,signal_handler_options=SignalHandlerOptions.NO);node=Tracker();stop=[False]
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stop.__setitem__(0,True))
    try:
        while rclpy.ok() and not stop[0]:rclpy.spin_once(node,timeout_sec=.05)
    finally:node.destroy_node();rclpy.try_shutdown()
