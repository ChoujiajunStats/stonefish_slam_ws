"""Thin ROS client, executed inside the current run's container."""
import argparse,json,time,os
from pathlib import Path
import yaml
import rclpy
from rclpy.node import Node
from rosgraph_msgs.msg import Clock
from uw_interfaces.msg import ControlRequest
from uw_interfaces.srv import Control


def main(args=None):
    p=argparse.ArgumentParser();p.add_argument('--run-dir',required=True)
    p.add_argument('action',choices=['status','arm','disarm','clear-fault','command'])
    p.add_argument('--velocity',nargs=4,type=float,default=[0.,0.,0.,0.]);p.add_argument('--seconds',type=float,default=1.)
    options=p.parse_args(args);folder=Path(options.run_dir);config=yaml.safe_load((folder/'resolved_config.yaml').read_text())
    if not 0<options.seconds<=30:raise ValueError('CLI commands must last 0..30 seconds')
    if config['control_mode']!='body_velocity' and options.action=='command':raise ValueError('Use explicit actuator_probe case for diagnostics')
    # docker exec inherits the container defaults, while launch uses the run's
    # resolved DDS domain. Join that same domain before creating a participant.
    os.environ['ROS_DOMAIN_ID']=str(config['ros_domain_id'])
    rclpy.init();node=Node('control_cli',namespace=config['namespace']);client=node.create_client(Control,'control/authority')
    publisher=node.create_publisher(ControlRequest,'control/request',1);clock=[None]
    node.create_subscription(Clock,'/clock',lambda m:clock.__setitem__(0,m.clock),1)
    try:
        if not client.wait_for_service(timeout_sec=5):raise RuntimeError('Control service unavailable')
        action={'status':'STATUS','arm':'ARM','disarm':'DISARM','clear-fault':'CLEAR_FAULT','command':'STATUS'}[options.action]
        future=client.call_async(Control.Request(run_id=folder.name,action=action,source='cli'))
        rclpy.spin_until_future_complete(node,future,timeout_sec=5)
        if not future.done():raise RuntimeError('Control service timed out')
        result=future.result();print(json.dumps(dict(accepted=result.accepted,state=result.state,reason=result.reason,source=result.source,generation=result.generation)))
        if not result.accepted:raise SystemExit(1)
        if options.action in ('arm','command'):
            if result.state!='ARMED' or result.source!='cli':raise RuntimeError('Explicit CLI ARM is required')
            deadline=time.monotonic()+options.seconds
            while time.monotonic()<deadline:
                rclpy.spin_once(node,timeout_sec=.02)
                if clock[0] is None:continue
                m=ControlRequest(run_id=folder.name,source='cli',token=result.token,generation=result.generation,
                    sequence=time.monotonic_ns(),issued_steady_ns=time.monotonic_ns())
                m.command.header.frame_id=config['namespace']+'/base_link';m.command.header.stamp=clock[0]
                m.command.twist.linear.x,m.command.twist.linear.y,m.command.twist.linear.z,m.command.twist.angular.z=options.velocity
                publisher.publish(m)
            future=client.call_async(Control.Request(run_id=folder.name,action='DISARM',source='cli'))
            rclpy.spin_until_future_complete(node,future,timeout_sec=2)
            print('Finite request ended; explicit DISARM sent.')
    finally:node.destroy_node();rclpy.try_shutdown()
