import math
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

import yaml

from uw_robot.description import make_urdf
from uw_robot.frames import (
    Q_FRD_FLU, attitude_to_enu_flu, frd_to_flu, ned_to_enu, normalized,
    qmul, rotate, rpy_quaternion, signed_permutation_covariance,
)

ROOT = Path(__file__).resolve().parents[1]


class FrameContractTests(unittest.TestCase):
    def assertVector(self, actual, expected):
        for a, b in zip(actual, expected):
            self.assertAlmostEqual(a, b, places=9)

    def test_axis_semantics(self):
        self.assertEqual(ned_to_enu((2, 3, 4)), (3, 2, -4))
        self.assertEqual(frd_to_flu((2, 3, 4)), (2, -3, -4))

    def test_north_heading_is_enu_positive_y(self):
        q = attitude_to_enu_flu((0, 0, 0, 1))
        self.assertVector(rotate(q, (1, 0, 0)), (0, 1, 0))
        self.assertVector(rotate(q, (0, 0, 1)), (0, 0, 1))

    def test_east_heading_is_enu_positive_x(self):
        q = attitude_to_enu_flu(rpy_quaternion(0, 0, math.pi/2))
        self.assertVector(rotate(q, (1, 0, 0)), (1, 0, 0))

    def test_attitude_conversion_commutes_with_vector_transform(self):
        for roll, pitch, yaw in ((0.3, -0.2, 1.4), (-1.1, 0.7, -2.8), (math.pi, 0, 0)):
            q_native = rpy_quaternion(roll, pitch, yaw)
            velocity_frd = (0.4, -0.8, 0.2)
            expected = ned_to_enu(rotate(q_native, velocity_frd))
            actual = rotate(attitude_to_enu_flu(q_native), frd_to_flu(velocity_frd))
            self.assertVector(actual, expected)

    def test_invalid_quaternion_fails(self):
        for q in ((0, 0, 0, 0), (float("nan"), 0, 0, 1)):
            with self.assertRaises(ValueError):
                normalized(q)

    def test_covariance_rotates_cross_terms(self):
        covariance = [4, 1, 2, 1, 9, 3, 2, 3, 16]
        actual = signed_permutation_covariance(covariance, (1, 0, 2), (1, 1, -1))
        self.assertEqual(actual, [9, 1, -3, 1, 4, -2, -3, -2, 16])

    def test_twist_covariance_preserves_translation_rotation_cross_terms(self):
        covariance = list(range(36))
        actual = signed_permutation_covariance(covariance, (0, 1, 2, 3, 4, 5), (1, -1, -1, 1, -1, -1))
        self.assertEqual(actual[4], -4)
        self.assertEqual(actual[10], 10)
        self.assertEqual(actual[18], 18)

    def test_unknown_covariance_sentinel_preserved(self):
        self.assertEqual(signed_permutation_covariance([-1]+[0]*8, (0, 1, 2), (1, -1, -1)), [-1]+[0]*8)

    def test_scene_camera_and_urdf_optical_axes_match(self):
        profile = yaml.safe_load((ROOT / "robot/config/bluerov2_heavy.yaml").read_text())
        urdf = ET.fromstring(make_urdf("test_rov", profile))
        for side, camera in profile["cameras"].items():
            joint = urdf.find(f"joint[@name='{side}_camera_optical_fixed']")
            optical_rpy = tuple(map(float, joint.find("origin").get("rpy").split()))
            public_rotation = rpy_quaternion(*optical_rpy)
            native_rotation = rpy_quaternion(*camera["rpy_frd"])
            for axis in ((1, 0, 0), (0, 1, 0), (0, 0, 1)):
                self.assertVector(rotate(public_rotation, axis), frd_to_flu(rotate(native_rotation, axis)))
        left, right = profile["cameras"]["left"], profile["cameras"]["right"]
        self.assertAlmostEqual(right["xyz_frd"][1]-left["xyz_frd"][1], profile["stereo_baseline_m"])

    def test_all_urdf_frames_are_namespaced(self):
        profile = yaml.safe_load((ROOT / "robot/config/bluerov2_heavy.yaml").read_text())
        root = ET.fromstring(make_urdf("rov22", profile))
        for link in root.findall("link"):
            self.assertTrue(link.get("name").startswith("rov22/"))
