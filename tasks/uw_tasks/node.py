"""Finite mission action, exclusive lifecycle and cancellation; no control algorithm."""
import copy,json,math,signal,time
from pathlib import Path
import yaml
import rclpy
from rclpy.node import Node
from rclpy.clock import Clock,ClockType
from rclpy.signals import SignalHandlerOptions
from rclpy.action import ActionServer,GoalResponse,CancelResponse
from rclpy.task import Future
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Path as PathMsg,Odometry
from std_msgs.msg import String
from visualization_msgs.msg import Marker
from uw_interfaces.action import ExecuteMission
from uw_interfaces.msg import NavigationGoal
from uw_interfaces.srv import Control
from uw_navigation.core import validate_waypoints,relative_goal,yaw


class Missions(Node):
    def __init__(self):
        super().__init__('missions');self.out=Path(self.declare_parameter('run_dir','').value)
        self.cfg=yaml.safe_load((self.out/'resolved_config.yaml').read_text());self.ns=self.cfg['namespace']
        self.p=yaml.safe_load((self.out/'tasks-parameters.yaml').read_text())
        self.guard={};self.guard_wall=0;self.nav={};self.nav_wall=0;self.terminal={};self.mission_handle=None;self.busy=False;self.used=set()
        self.future=None;self.arm_future=None;self.stop_future=None;self.started=0;self.index=0;self.sequence=0;self.token='';self.generation=0
        self.estimate=None;self.estimate_wall=0;self.resolved=[]
        self.phase='IDLE';self.reason='';self.outcome='';self.stop_wall=0;self.epoch=0
        self.goal_pub=self.create_publisher(NavigationGoal,'navigation/goal',1);self.path_pub=self.create_publisher(PathMsg,'navigation/path',1)
        self.marker=self.create_publisher(Marker,'mission/status_marker',1)
        self.status=self.create_publisher(String,'mission/status',1);self.client=self.create_client(Control,'control/authority')
        self.create_subscription(String,'control/status',self.on_guard,1);self.create_subscription(String,'navigation/status',self.on_nav,1)
        self.create_subscription(String,'sim/terminal/status',lambda m:setattr(self,'terminal',json.loads(m.data)),1)
        self.create_subscription(Odometry,'state/odometry',self.on_estimate,1)
        self.server=ActionServer(self,ExecuteMission,'mission/execute',self.execute,goal_callback=self.accept,cancel_callback=self.cancel,handle_accepted_callback=self.accepted)
        self.create_timer(1/self.p['heartbeat_hz'],self.tick,clock=Clock(clock_type=ClockType.STEADY_TIME))
    def on_estimate(self,m):self.estimate=m;self.estimate_wall=time.monotonic_ns()
    def on_guard(self,m):self.guard=json.loads(m.data);self.guard_wall=time.monotonic_ns()
    def on_nav(self,m):self.nav=json.loads(m.data);self.nav_wall=time.monotonic_ns()
    def event(self,event,**fields):
        with (self.out/'mission-events.jsonl').open('a') as f:f.write(json.dumps(dict(event=event,wall_ns=time.monotonic_ns(),**fields))+'\n')
    def accept(self,g):
        points=[(p.header.frame_id,[p.pose.position.x,p.pose.position.y,p.pose.position.z],[p.pose.orientation.x,p.pose.orientation.y,p.pose.orientation.z,p.pose.orientation.w]) for p in g.waypoints]
        error=validate_waypoints(g.run_id,self.out.name,g.mission_id,g.authorize_arm,points,g.timeout_sec,[self.ns+'/odom',self.ns+'/mission_start'],self.p)
        if not error and (self.estimate is None or time.monotonic_ns()-self.estimate_wall>250_000_000):error='estimate_stale'
        if not error and (self.busy or g.mission_id in self.used):error='busy_or_replayed_mission'
        if not error and (time.monotonic_ns()-self.guard_wall>250_000_000 or not self.guard.get('ready') or self.guard.get('state')!='DISARMED'):error='guard_not_ready_disarmed'
        self.event('goal_rejected' if error else 'goal_accepted',mission_id=g.mission_id,reason=error)
        if error:return GoalResponse.REJECT
        self.resolved=copy.deepcopy(list(g.waypoints));origin=self.estimate.pose.pose.position;oq=self.estimate.pose.pose.orientation
        for p in self.resolved:
            if p.header.frame_id==self.ns+'/mission_start':
                v=p.pose.position;q=p.pose.orientation
                xyz,a=relative_goal([v.x,v.y,v.z],yaw([q.x,q.y,q.z,q.w]),[origin.x,origin.y,origin.z],yaw([oq.x,oq.y,oq.z,oq.w]))
                v.x,v.y,v.z=xyz;q.z=math.sin(a/2);q.w=math.cos(a/2);p.header.frame_id=self.ns+'/odom'
        self.event('mission_frame_resolved',mission_id=g.mission_id,origin_position=[origin.x,origin.y,origin.z],origin_quaternion=[oq.x,oq.y,oq.z,oq.w],
            odom_goals=[[p.pose.position.x,p.pose.position.y,p.pose.position.z,p.pose.orientation.z,p.pose.orientation.w] for p in self.resolved])
        self.busy=True;self.used.add(g.mission_id);return GoalResponse.ACCEPT
    def accepted(self,handle):
        self.mission_handle=handle;self.future=Future();self.phase='ARMING';self.started=time.monotonic_ns();self.index=0;self.sequence=0
        self.epoch=self.guard['epoch'];self.reason='';self.outcome='';self.token='';self.stop_future=None
        self.arm_future=self.client.call_async(Control.Request(run_id=self.out.name,action='ARM',source='navigation'))
        path=PathMsg();path.header.frame_id=self.ns+'/odom';path.poses=self.resolved;self.path_pub.publish(path)
        handle.execute()
    async def execute(self,handle):return await self.future
    def cancel(self,handle):
        self.event('cancel_requested',mission_id=handle.request.mission_id)
        return CancelResponse.ACCEPT if handle==self.mission_handle and self.busy else CancelResponse.REJECT
    def stopping(self,outcome,reason):
        if self.phase=='STOPPING':return
        self.phase='STOPPING';self.outcome=outcome;self.reason=reason;self.stop_wall=time.monotonic_ns()
        action='FAULT' if outcome=='ABORTED' and reason not in ('mission_timeout','arm_rejected') else 'DISARM'
        self.stop_future=self.client.call_async(Control.Request(run_id=self.out.name,action=action,source='navigation'))
        self.event('stopping',outcome=outcome,reason=reason)
    def complete(self,neutral):
        result=ExecuteMission.Result(outcome=self.outcome,reason=self.reason,completed_waypoints=self.index,
            elapsed_sec=(time.monotonic_ns()-self.started)*1e-9,terminal_neutral_verified=neutral)
        if not neutral:result.outcome='ABORTED';result.reason+=';terminal_neutral_not_verified'
        if result.outcome=='SUCCEEDED':self.mission_handle.succeed()
        elif result.outcome=='CANCELED' and self.mission_handle.is_cancel_requested:self.mission_handle.canceled()
        else:self.mission_handle.abort()
        self.event('result',outcome=result.outcome,reason=result.reason,completed=self.index,terminal_neutral_verified=neutral)
        self.future.set_result(result);self.phase=result.outcome;self.busy=False;self.mission_handle=None
    def tick(self):
        now=time.monotonic_ns()
        if self.busy and self.mission_handle:
            g=self.mission_handle.request
            if self.phase=='ARMING' and self.arm_future.done():
                r=self.arm_future.result();self.arm_future=None
                if r.accepted:self.token=r.token;self.generation=r.generation;self.phase='RUNNING'
                else:self.stopping('ABORTED','arm_rejected')
            if self.phase in ('ARMING','RUNNING'):
                if self.mission_handle.is_cancel_requested:self.stopping('CANCELED','explicit_cancel')
                elif now-self.started>int(g.timeout_sec*1e9):self.stopping('ABORTED','mission_timeout')
                elif self.phase=='RUNNING' and (now-self.guard_wall>250_000_000 or self.guard.get('state')=='FAULT' or self.guard.get('epoch')!=self.epoch):self.stopping('ABORTED','control_or_estimator_fault')
            if self.phase=='RUNNING':
                # Allow the first status from Guard to catch up to the service response.
                if self.guard.get('state')=='DISARMED' and now-self.started>1_000_000_000:self.stopping('ABORTED','authority_revoked')
                elif (self.nav.get('mission_id')==g.mission_id and self.nav.get('generation')==self.generation and self.nav.get('waypoint_index')==self.index and now-self.nav_wall<250_000_000 and self.nav.get('reached')):
                    self.event('waypoint_reached',index=self.index,distance_m=self.nav['distance_m']);self.index+=1
                    if self.index==len(g.waypoints):self.stopping('SUCCEEDED','all_waypoints_settled')
                if self.phase=='RUNNING':
                    self.sequence+=1
                    target=NavigationGoal(target=self.resolved[self.index],run_id=self.out.name,mission_id=g.mission_id,token=self.token,
                        generation=self.generation,epoch=self.epoch,sequence=self.sequence,issued_steady_ns=now,
                        deadline_steady_ns=self.started+int(g.timeout_sec*1e9),waypoint_index=self.index)
                    self.goal_pub.publish(target)
            if self.phase=='STOPPING':
                # An outstanding ARM must settle before acknowledging cancel; prevents late ARM.
                arm_pending=self.arm_future is not None and not self.arm_future.done()
                if self.arm_future is not None and self.arm_future.done():
                    r=self.arm_future.result();self.arm_future=None
                    self.stop_future=self.client.call_async(Control.Request(run_id=self.out.name,action='DISARM',source='navigation'))
                neutral=(not arm_pending and self.terminal.get('state') in ('DISARMED','FAULT') and
                    int(self.terminal.get('wall_ns',0))>=self.stop_wall and all(abs(float(v))<1e-9 for v in self.terminal.get('receiver_setpoint',[1])))
                if neutral or now-self.stop_wall>int(self.p['neutralization_deadline_sec']*1e9):self.complete(neutral)
            if self.mission_handle:
                self.mission_handle.publish_feedback(ExecuteMission.Feedback(state=self.phase,waypoint_index=self.index,
                    distance_m=float(self.nav.get('distance_m',0)),elapsed_sec=(now-self.started)*1e-9))
        report=dict(run=self.out.name,wall_ns=now,state=self.phase,busy=self.busy,waypoint_index=self.index,reason=self.reason,
            mission_id=self.mission_handle.request.mission_id if self.mission_handle else '',elapsed_sec=(now-self.started)*1e-9 if self.started else 0.)
        self.status.publish(String(data=json.dumps(report)))
        marker=Marker();marker.header.frame_id=self.ns+'/odom';marker.ns='mission';marker.id=0;marker.type=Marker.TEXT_VIEW_FACING;marker.action=Marker.ADD
        marker.pose.orientation.w=1.;marker.pose.position.z=.6;marker.scale.z=.15;marker.color.a=1.;marker.color.g=.9;marker.color.r=.9
        marker.text=f'{self.phase}\nWP{self.index}';self.marker.publish(marker)
        temporary=self.out/'mission-status.json.tmp';temporary.write_text(json.dumps(report));temporary.replace(self.out/'mission-status.json')


def main(args=None):
    rclpy.init(args=args,signal_handler_options=SignalHandlerOptions.NO);node=Missions();stop=[False]
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stop.__setitem__(0,True))
    try:
        while rclpy.ok() and not stop[0]:rclpy.spin_once(node,timeout_sec=.05)
    finally:node.server.destroy();node.destroy_node();rclpy.try_shutdown()
