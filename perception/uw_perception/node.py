"""M2 sensor validation and exact stereo pairing, independent of truth and control."""
import json
import signal
import time
from pathlib import Path
import yaml
import rclpy
from rclpy.node import Node
from rclpy.clock import Clock, ClockType
from rclpy.signals import SignalHandlerOptions
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image, Imu, CameraInfo
from std_msgs.msg import String
from rosgraph_msgs.msg import Clock as ClockMsg
from uw_robot.frames import frd_to_flu, signed_permutation_covariance
from uw_perception.contracts import ExactPairs, intrinsics, valid_imu


def ns(stamp):
    return stamp.sec*1_000_000_000+stamp.nanosec


class Sensors(Node):
    def __init__(self):
        super().__init__('m2_sensors')
        self.folder = Path(self.declare_parameter('run_dir', '').value)
        self.config = yaml.safe_load((self.folder/'resolved_config.yaml').read_text())
        self.profile = yaml.safe_load((self.folder/'robot_profile.yaml').read_text())
        self.prefix = self.config['namespace']
        self.pairs = ExactPairs()
        self.counts = dict(imu=0, stereo=0, rejected=0, throttled=0)
        self.clock_ns = None
        self.last_imu = -1
        self.last_published_pair = -1
        self.fault = ''
        self.mask = ''
        self.imu_pub = self.create_publisher(Imu, 'sensors/imu', qos_profile_sensor_data)
        self.images, self.infos = [], []
        for side, name in enumerate(('left', 'right')):
            self.images.append(self.create_publisher(Image, f'sensors/stereo/{name}/image_raw', qos_profile_sensor_data))
            self.infos.append(self.create_publisher(CameraInfo, f'sensors/stereo/{name}/camera_info', qos_profile_sensor_data))
            self.create_subscription(Image, f'sim/raw/{name}/image_color', lambda m, s=side: self.image(m, s), qos_profile_sensor_data)
        self.create_subscription(Imu, 'sim/raw/imu_frd', self.imu, qos_profile_sensor_data)
        self.create_subscription(ClockMsg, '/clock', self.on_clock, qos_profile_sensor_data)
        self.create_subscription(String, 'perception/fixture', self.fixture, 1)
        self.status = self.create_publisher(String, 'perception/status', 1)
        self.create_timer(.2, self.report, clock=Clock(clock_type=ClockType.STEADY_TIME))

    def on_clock(self, msg):
        stamp = ns(msg.clock)
        if self.clock_ns is not None and stamp < self.clock_ns:
            self.fault = 'CLOCK_REWIND_RESTART_REQUIRED'
            self.pairs = ExactPairs()
        self.clock_ns = stamp

    def fixture(self, msg):
        # Only the explicit diagnostic config accepts scoped sensor-loss injection.
        if self.config['evaluation_phase'] == 'manual':
            return
        try:
            p = json.loads(msg.data)
            session = json.loads((self.folder/'session.json').read_text())
            if (p['run'] == self.folder.name and p['secret'] == session['terminal_secret']
                    and 0 <= time.monotonic_ns()-p['sent_ns'] < 250_000_000
                    and p['op'] in ('drop_images', 'drop_imu', 'restore')):
                self.mask = '' if p['op'] == 'restore' else p['op']
        except (ValueError, KeyError):
            self.counts['rejected'] += 1

    def imu(self, msg):
        stamp = ns(msg.header.stamp)
        a = msg.linear_acceleration
        w = msg.angular_velocity
        if (self.fault or stamp <= self.last_imu or not valid_imu(
                (a.x,a.y,a.z), (w.x,w.y,w.z), msg.orientation_covariance,
                msg.header.frame_id, self.prefix+'/imu_filter')):
            self.counts['rejected'] += 1
            return
        self.last_imu = stamp
        if self.mask == 'drop_imu':
            return
        a.x,a.y,a.z = frd_to_flu((a.x,a.y,a.z))
        w.x,w.y,w.z = frd_to_flu((w.x,w.y,w.z))
        msg.orientation.x = msg.orientation.y = msg.orientation.z = 0.
        msg.orientation.w = 1.
        msg.orientation_covariance = [-1.]+[0.]*8
        for field in ('angular_velocity_covariance', 'linear_acceleration_covariance'):
            setattr(msg, field, signed_permutation_covariance(getattr(msg, field), (0,1,2), (1,-1,-1)))
        msg.header.frame_id = self.prefix+'/imu_link'
        self.imu_pub.publish(msg)
        self.counts['imu'] += 1

    def image(self, msg, side):
        expected = self.profile['cameras'][('left','right')[side]]
        stamp = ns(msg.header.stamp)
        if (self.fault or msg.encoding != 'rgb8' or msg.width != expected['width']
                or msg.height != expected['height'] or msg.step != msg.width*3
                or len(msg.data) != msg.step*msg.height or stamp <= 0
                or msg.header.frame_id != self.prefix+'/camera_'+('left','right')[side]):
            self.counts['rejected'] += 1
            return
        pair = self.pairs.add(side, stamp, msg)
        if pair is None:
            return
        # Both native cameras render the same snapshot continuously. Limit paired VIO
        # delivery to <=20Hz by dropping whole pairs; retained acquisition stamps stay exact.
        if stamp-self.last_published_pair < 50_000_000:
            self.counts['throttled'] += 1
            return
        self.last_published_pair = stamp
        if self.mask == 'drop_images':
            return
        for index, image in enumerate(pair):
            name = ('left','right')[index]
            image.header.frame_id = self.prefix+'/'+name+'_camera_optical'
            info = CameraInfo(header=image.header, width=image.width, height=image.height,
                              distortion_model='plumb_bob', d=[0.]*5)
            fx,fy,cx,cy = intrinsics(image.width,image.height,expected['horizontal_fov_deg'])
            info.k = [fx,0.,cx,0.,fy,cy,0.,0.,1.]
            info.r = [1.,0.,0.,0.,1.,0.,0.,0.,1.]
            info.p = [fx,0.,cx,-fx*self.profile['stereo_baseline_m']*index,0.,fy,cy,0.,0.,0.,1.,0.]
            self.images[index].publish(image)
            self.infos[index].publish(info)
        self.counts['stereo'] += 1

    def report(self):
        self.status.publish(String(data=json.dumps(dict(run=self.folder.name,
            wall_ns=time.monotonic_ns(),state='FAULT' if self.fault else 'RUNNING',
            reason=self.fault,counts=self.counts,pair_drops=self.pairs.dropped,
            imu_stamp_ns=self.last_imu,pair_stamp_ns=self.last_published_pair,
            imu_semantics='SPECIFIC_FORCE_FLU_NO_ORIENTATION',synchronization='SAME_RENDER_SNAPSHOT'))))


def main(args=None):
    rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
    node = Sensors()
    stop = [False]
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.__setitem__(0, True))
    try:
        while rclpy.ok() and not stop[0]:
            rclpy.spin_once(node, timeout_sec=.1)
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
