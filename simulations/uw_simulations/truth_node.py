"""M2 evaluator/excitation truth only. No state/odometry publisher and no TF."""
import signal
import rclpy
from rclpy.node import Node
from rclpy.signals import SignalHandlerOptions
from rclpy.qos import qos_profile_sensor_data
from nav_msgs.msg import Odometry
from uw_robot.frames import attitude_to_enu_flu,frd_to_flu,ned_to_enu,signed_permutation_covariance


class Truth(Node):
    def __init__(self):
        super().__init__('m2_debug_truth')
        self.prefix=self.declare_parameter('frame_prefix','rov01').value+'/truth'
        self.pub=self.create_publisher(Odometry,'sim/ground_truth/odometry',5)
        self.create_subscription(Odometry,'sim/raw/odometry_ned',self.receive,qos_profile_sensor_data)
    def receive(self,m):
        p=m.pose.pose.position;q=m.pose.pose.orientation;v=m.twist.twist.linear;w=m.twist.twist.angular
        p.x,p.y,p.z=ned_to_enu((p.x,p.y,p.z));q.x,q.y,q.z,q.w=attitude_to_enu_flu((q.x,q.y,q.z,q.w))
        v.x,v.y,v.z=frd_to_flu((v.x,v.y,v.z));w.x,w.y,w.z=frd_to_flu((w.x,w.y,w.z))
        m.pose.covariance=signed_permutation_covariance(m.pose.covariance,(1,0,2,4,3,5),(1,1,-1,1,1,-1))
        m.twist.covariance=signed_permutation_covariance(m.twist.covariance,(0,1,2,3,4,5),(1,-1,-1,1,-1,-1))
        m.header.frame_id=self.prefix+'/odom';m.child_frame_id=self.prefix+'/base_link'
        self.pub.publish(m)


def main(args=None):
    rclpy.init(args=args,signal_handler_options=SignalHandlerOptions.NO);node=Truth();stop=[False]
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stop.__setitem__(0,True))
    try:
        while rclpy.ok() and not stop[0]:rclpy.spin_once(node,timeout_sec=.1)
    finally:
        node.destroy_node()
        if rclpy.ok():rclpy.shutdown()
