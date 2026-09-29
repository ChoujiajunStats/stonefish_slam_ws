"""M0 privileged observations. No actuator publisher or subscriber."""

import copy
import json
import time
from std_msgs.msg import String
from pathlib import Path

import signal
import rclpy
from rclpy.signals import SignalHandlerOptions
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from geometry_msgs.msg import TransformStamped
from nav_msgs.msg import Odometry
from sensor_msgs.msg import CameraInfo, Image, Imu
from tf2_ros import TransformBroadcaster
import yaml

from uw_robot.frames import (
    attitude_to_enu_flu, frd_to_flu, ned_to_enu, signed_permutation_covariance,
)


def _vector(value):
    return value.x, value.y, value.z


def _set_vector(value, xyz):
    value.x, value.y, value.z = xyz


def _set_attitude(value):
    value.x, value.y, value.z, value.w = attitude_to_enu_flu((value.x, value.y, value.z, value.w))


class ObservationAdapter(Node):
    def __init__(self):
        super().__init__("observation_adapter")
        self.prefix = self.declare_parameter("frame_prefix", "rov01").value
        profile_path = self.declare_parameter("robot_profile_path", "").value
        self.profile = yaml.safe_load(Path(profile_path).read_text())
        access = self.declare_parameter("observation_access", "").value
        if access != "PRIVILEGED_DEBUG":
            raise ValueError("M0 state source requires explicit PRIVILEGED_DEBUG")
        self.run_dir = self.declare_parameter('run_dir','').value
        self.freeze_state = False
        self.frozen_state = None
        if self.run_dir:
            self.create_subscription(String,'sim/observation/fixture',self.on_fixture,1)
        self.tf = TransformBroadcaster(self)
        self.gt = self.create_publisher(Odometry, "sim/ground_truth/odometry", 5)
        self.state = self.create_publisher(Odometry, "state/odometry", 5)
        self.imu = self.create_publisher(Imu, "sensors/imu", qos_profile_sensor_data)
        self.create_subscription(Odometry, "sim/raw/odometry_ned", self.on_odometry, qos_profile_sensor_data)
        self.create_subscription(Imu, "sim/raw/imu_frd", self.on_imu, qos_profile_sensor_data)
        self.images, self.infos = {}, {}
        for side in ("left", "right"):
            self.images[side] = self.create_publisher(Image, f"sensors/stereo/{side}/image_raw", qos_profile_sensor_data)
            self.infos[side] = self.create_publisher(CameraInfo, f"sensors/stereo/{side}/camera_info", qos_profile_sensor_data)
            self.create_subscription(Image, f"sim/raw/{side}/image_color",
                                     lambda msg, side=side: self.on_image(msg, side), qos_profile_sensor_data)
            self.create_subscription(CameraInfo, f"sim/raw/{side}/camera_info",
                                     lambda msg, side=side: self.on_info(msg, side), qos_profile_sensor_data)
        self.get_logger().warning("PRIVILEGED_DEBUG: state/odometry is simulation truth")

    def on_fixture(self,msg):
        try:
            p=json.loads(msg.data)
            secret=json.loads((Path(self.run_dir)/'session.json').read_text())['terminal_secret']
            if p['run']==Path(self.run_dir).name and p['secret']==secret and 0<=time.monotonic_ns()-p['sent_ns']<250_000_000:
                self.freeze_state=p['op']=='freeze_state'
        except (ValueError,KeyError):pass

    def on_odometry(self, msg):
        _set_vector(msg.pose.pose.position, ned_to_enu(_vector(msg.pose.pose.position)))
        _set_attitude(msg.pose.pose.orientation)
        _set_vector(msg.twist.twist.linear, frd_to_flu(_vector(msg.twist.twist.linear)))
        _set_vector(msg.twist.twist.angular, frd_to_flu(_vector(msg.twist.twist.angular)))
        msg.pose.covariance = signed_permutation_covariance(
            msg.pose.covariance, (1, 0, 2, 4, 3, 5), (1, 1, -1, 1, 1, -1))
        msg.twist.covariance = signed_permutation_covariance(
            msg.twist.covariance, (0, 1, 2, 3, 4, 5), (1, -1, -1, 1, -1, -1))
        msg.header.frame_id = f"{self.prefix}/odom"
        msg.child_frame_id = f"{self.prefix}/base_link"
        self.gt.publish(msg)
        if not self.freeze_state:self.frozen_state=copy.deepcopy(msg)
        self.state.publish(self.frozen_state or msg)
        transform = TransformStamped()
        transform.header = copy.deepcopy(msg.header)
        transform.child_frame_id = msg.child_frame_id
        _set_vector(transform.transform.translation, _vector(msg.pose.pose.position))
        transform.transform.rotation = copy.deepcopy(msg.pose.pose.orientation)
        self.tf.sendTransform(transform)

    def on_imu(self, msg):
        _set_attitude(msg.orientation)
        _set_vector(msg.angular_velocity, frd_to_flu(_vector(msg.angular_velocity)))
        _set_vector(msg.linear_acceleration, frd_to_flu(_vector(msg.linear_acceleration)))
        for field in ("orientation_covariance", "angular_velocity_covariance", "linear_acceleration_covariance"):
            setattr(msg, field, signed_permutation_covariance(getattr(msg, field), (0, 1, 2), (1, -1, -1)))
        msg.header.frame_id = f"{self.prefix}/imu_link"
        self.imu.publish(msg)

    def on_image(self, msg, side):
        msg.header.frame_id = f"{self.prefix}/{side}_camera_optical"
        self.images[side].publish(msg)

    def on_info(self, msg, side):
        msg.header.frame_id = f"{self.prefix}/{side}_camera_optical"
        # Canonical parallel stereo, in metres; upstream v1.3 leaves this zero.
        msg.p[3] = -msg.p[0]*self.profile["stereo_baseline_m"] if side == "right" else 0.0
        self.infos[side].publish(msg)


def main(args=None):
    rclpy.init(args=args,signal_handler_options=SignalHandlerOptions.NO)
    node = ObservationAdapter()
    stop = [False]
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.__setitem__(0, True))
    try:
        while rclpy.ok() and not stop[0]:
            rclpy.spin_once(node, timeout_sec=0.1)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
