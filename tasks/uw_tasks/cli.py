"""Explicit finite mission client; Ctrl+C requests action cancellation."""
import argparse,json,math,os,time,uuid
from pathlib import Path
import yaml
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from action_msgs.srv import CancelGoal
from geometry_msgs.msg import PoseStamped
from uw_interfaces.action import ExecuteMission


def main():
    p=argparse.ArgumentParser();p.add_argument('--run-dir',required=True);p.add_argument('action',choices=['mission','mission-cancel'])
    p.add_argument('--arm',action='store_true');p.add_argument('--waypoint',nargs=4,type=float,action='append');p.add_argument('--timeout',type=float,default=60.)
    a=p.parse_args();out=Path(a.run_dir);cfg=yaml.safe_load((out/'resolved_config.yaml').read_text())
    os.environ['ROS_DOMAIN_ID']=str(cfg['ros_domain_id']);rclpy.init();node=Node('mission_cli',namespace=cfg['namespace'])
    def wait(f,limit):
        start=time.monotonic()
        while not f.done() and time.monotonic()-start<limit:rclpy.spin_once(node,timeout_sec=.05)
        if not f.done():raise RuntimeError('Mission service/action timeout')
        return f.result()
    try:
        if a.action=='mission-cancel':
            c=node.create_client(CancelGoal,'mission/execute/_action/cancel_goal')
            if not c.wait_for_service(timeout_sec=3):raise RuntimeError('No mission server')
            result=wait(c.call_async(CancelGoal.Request()),3)
            print(json.dumps(dict(return_code=result.return_code,canceling=len(result.goals_canceling))));return
        if not a.arm or not a.waypoint:raise ValueError('Explicit --arm and at least one --waypoint x y z yaw_rad required')
        c=ActionClient(node,ExecuteMission,'mission/execute')
        if not c.wait_for_server(timeout_sec=3):raise RuntimeError('No mission server')
        g=ExecuteMission.Goal(run_id=out.name,mission_id='cli_'+uuid.uuid4().hex,authorize_arm=True,timeout_sec=a.timeout)
        for x,y,z,angle in a.waypoint:
            q=PoseStamped();q.header.frame_id=cfg['namespace']+'/mission_start';q.pose.position.x=x;q.pose.position.y=y;q.pose.position.z=z
            q.pose.orientation.z=math.sin(angle/2);q.pose.orientation.w=math.cos(angle/2);g.waypoints.append(q)
        h=wait(c.send_goal_async(g),3)
        if not h.accepted:raise RuntimeError('Mission rejected; check status and mission-events.jsonl')
        print(json.dumps(dict(accepted=True,mission_id=g.mission_id)),flush=True)
        try:r=wait(h.get_result_async(),a.timeout+3)
        except KeyboardInterrupt:
            wait(h.cancel_goal_async(),3);r=wait(h.get_result_async(),3)
        value=r.result;print(json.dumps(dict(ros_status=r.status,outcome=value.outcome,reason=value.reason,completed=value.completed_waypoints,neutral=value.terminal_neutral_verified)))
        if value.outcome!='SUCCEEDED':raise SystemExit(1)
    finally:node.destroy_node();rclpy.try_shutdown()
