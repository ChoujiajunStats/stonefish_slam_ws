"""Finite M0 observation acceptance driven by steady time, never fixed sleeps."""

import json
import math
from pathlib import Path
import time

import rclpy
from rclpy.clock import Clock, ClockType
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rclpy.time import Time
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from nav_msgs.msg import Odometry
from rosgraph_msgs.msg import Clock as ClockMsg
from sensor_msgs.msg import CameraInfo, Image, Imu
from tf2_ros import Buffer, TransformListener


def stamp_seconds(stamp):
    return stamp.sec + stamp.nanosec*1e-9


class Probe(Node):
    result_file = 'metrics.json'
    ready_file = 'ready.json'
    scope = 'M0_observation_probe'
    forbidden_topics = ('actuators/thrusters', 'setpoint/pwm')
    ready_message = 'PRIVILEGED_DEBUG; control disabled'
    def __init__(self):
        super().__init__("m0_probe")
        self.output = Path(self.declare_parameter("run_dir", "").value)
        self.prefix = self.declare_parameter("frame_prefix", "rov01").value
        self.startup_timeout = self.declare_parameter("startup_timeout_sec", 45.0).value
        self.duration = self.declare_parameter("duration_sec", 60.0).value
        self.started = time.monotonic()
        self.ready_at = None
        self.clock_value = None
        self.first_clock = None
        self.clock_changed_at = None
        self.observed = {}
        self.errors = []
        self.done = False
        self.result_code = 1
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.diagnostics = self.create_publisher(DiagnosticArray, "diagnostics", 5)
        self.create_subscription(ClockMsg, "/clock", self.on_clock, qos_profile_sensor_data)
        specs = {
            "state/odometry": (Odometry, "odom"),
            "sensors/imu": (Imu, "imu_link"),
            **{f"sensors/stereo/{side}/{kind}": (cls, f"{side}_camera_optical")
               for side in ("left", "right") for kind, cls in (("image_raw", Image), ("camera_info", CameraInfo))},
        }
        for topic, (cls, frame) in specs.items():
            self.create_subscription(cls, topic, lambda msg, t=topic, f=frame: self.on_message(msg, t, f),
                                     qos_profile_sensor_data)
        self.expected = set(specs)
        self.create_timer(0.2, self.check, clock=Clock(clock_type=ClockType.STEADY_TIME))

    def on_clock(self, msg):
        value = stamp_seconds(msg.clock)
        if self.first_clock is None:
            self.first_clock = value
        if self.clock_value is not None and value < self.clock_value:
            self.errors.append("Simulation clock moved backwards; use a new process for reset")
        if self.clock_value != value:
            self.clock_changed_at = time.monotonic()
        self.clock_value = value

    def on_message(self, msg, topic, frame):
        if msg.header.frame_id != f"{self.prefix}/{frame}":
            self.errors.append(f"Wrong frame on {topic}: {msg.header.frame_id}")
        if isinstance(msg, Image):
            if (msg.encoding != "rgb8" or (msg.width, msg.height) != (640, 480)
                    or msg.step != msg.width*3 or len(msg.data) != msg.step*msg.height):
                self.errors.append(f"Invalid image shape/encoding on {topic}")
        if isinstance(msg, CameraInfo):
            expected_tx = -msg.p[0]*0.145 if "/right/" in topic else 0.0
            if (not all(math.isfinite(x) for x in (*msg.k, *msg.p))
                    or msg.p[0] <= 0 or abs(msg.p[3]-expected_tx) > 1e-6
                    or (msg.width, msg.height) != (640, 480)):
                self.errors.append(f"Invalid stereo projection on {topic}")
        if isinstance(msg, Odometry):
            p, q = msg.pose.pose.position, msg.pose.pose.orientation
            if msg.child_frame_id != f"{self.prefix}/base_link":
                self.errors.append("Wrong odometry child frame")
            if (not all(math.isfinite(x) for x in (p.x, p.y, p.z, q.x, q.y, q.z, q.w))
                    or abs(sum(x*x for x in (q.x, q.y, q.z, q.w))-1) > 1e-5):
                self.errors.append("Invalid odometry pose")
        if isinstance(msg, Imu):
            q, v, a = msg.orientation, msg.angular_velocity, msg.linear_acceleration
            if (not all(math.isfinite(x) for x in (q.x, q.y, q.z, q.w, v.x, v.y, v.z, a.x, a.y, a.z))
                    or abs(sum(x*x for x in (q.x, q.y, q.z, q.w))-1) > 1e-5):
                self.errors.append("Invalid IMU sample")
        old = self.observed.get(topic, {})
        stamp = stamp_seconds(msg.header.stamp)
        if stamp < old.get("stamp", 0):
            self.errors.append(f"Message time moved backwards: {topic}")
        self.observed[topic] = {"count": old.get("count", 0)+1, "stamp": stamp,
                                "last_wall": time.monotonic(), "frame": msg.header.frame_id}

    def finish(self, passed, reason):
        result = {"status": "PASS" if passed else "FAIL", "scope": self.scope,
                  "reason": reason, "errors": sorted(set(self.errors)),
                  "wall_duration_sec": time.monotonic()-self.started,
                  "clock_first_sec": self.first_clock,
                  "clock_sec": self.clock_value, "topics": self.observed,
                  "unverified": ["GPU visual correctness", "stereo exposure synchronization",
                                 "IMU physical fidelity", "control", "estimation", "restart acceptance"]}
        (self.output / self.result_file).write_text(json.dumps(result, indent=2)+"\n")
        self.result_code = 0 if passed else 1
        self.done = True

    def check(self):
        if self.done:
            return
        now = time.monotonic()
        clock_count = self.count_publishers("/clock")
        if clock_count > 1:
            self.errors.append("Multiple /clock publishers in the DDS domain")
        for topic in self.forbidden_topics:
            if self.count_publishers(topic) or self.count_subscribers(topic):
                self.errors.append(f"Actuator endpoint present in M0: {topic}")
        fresh = (self.expected == set(self.observed) and self.clock_changed_at is not None
                 and now-self.clock_changed_at < 2 and clock_count == 1
                 and all(now-v["last_wall"] < 2 and v["stamp"] > 0
                         and abs(v["stamp"]-self.clock_value) < 1 for v in self.observed.values()))
        frames = ("base_link", "imu_link", "left_camera_optical", "right_camera_optical")
        tf_ready = all(self.tf_buffer.can_transform(f"{self.prefix}/odom", f"{self.prefix}/{f}", Time()) for f in frames)
        ready = fresh and tf_ready
        if ready and self.ready_at is None:
            self.ready_at = now
            (self.output / self.ready_file).write_text(json.dumps({"ready": True, "wall_time": now})+"\n")
        status = DiagnosticStatus()
        status.name = f"{self.prefix}/m0_observation"
        status.hardware_id = "stonefish_simulation"
        status.level = DiagnosticStatus.OK if ready else DiagnosticStatus.WARN
        status.message = self.ready_message if ready else "Waiting for clock, sensors and TF"
        status.values = [KeyValue(key="control_enabled", value="false")]
        array = DiagnosticArray()
        array.header.stamp = self.get_clock().now().to_msg()
        array.status = [status]
        self.diagnostics.publish(array)
        if self.errors:
            self.finish(False, "Contract or authority violation")
        elif self.ready_at is None and now-self.started > self.startup_timeout:
            self.finish(False, "Startup readiness timed out")
        elif self.ready_at is not None and not ready:
            self.finish(False, "Observation or clock lost after readiness")
        elif self.ready_at is not None and now-self.ready_at >= self.duration:
            self.finish(True, "Finite M0 observation window completed")


def main(args=None):
    rclpy.init(args=args)
    node = Probe()
    try:
        while rclpy.ok() and not node.done:
            rclpy.spin_once(node, timeout_sec=0.2)
        code = node.result_code
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    raise SystemExit(code)
