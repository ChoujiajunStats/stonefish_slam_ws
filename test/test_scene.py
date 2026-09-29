import hashlib
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

import yaml

from uw_simulations.scene import generate_scene

ROOT = Path(__file__).resolve().parents[1]


class SceneContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.upstream = self.root / "upstream"
        (self.upstream / "scenarios").mkdir(parents=True)
        (self.upstream / "data").mkdir()
        self.profile = yaml.safe_load((ROOT / "robot/config/bluerov2_heavy.yaml").read_text())
        root = ET.Element("scenario")
        ET.SubElement(root, "looks")
        robot = ET.SubElement(root, "robot", name="$(arg vehicle_name)")
        ET.SubElement(robot, "world_transform", xyz="$(arg position)", rpy="$(arg orientation)")
        ET.SubElement(robot, "ros_subscriber", thrusters="/bluerov2/setpoint/pwm")
        for name in self.profile["thruster_order"]:
            ET.SubElement(robot, "actuator", name=name, type="thruster")
        for name in ("odometry", "imu_filter", "camera_left", "camera_right", "gps", "dvl"):
            sensor = ET.SubElement(robot, "sensor", name=name)
            ET.SubElement(sensor, "ros_publisher", topic="/old/topic")
            ET.SubElement(sensor, "origin", xyz="0 0 0", rpy="0 0 0")
            ET.SubElement(sensor, "specs")
        ET.SubElement(robot, "mesh", filename="robot.obj")
        (self.upstream / "data/robot.obj").write_text("# fixture mesh\n")
        self.source = self.upstream / "scenarios/bluerov2.scn"
        ET.ElementTree(root).write(self.source)
        self.profile["upstream_scene_sha256"] = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.output = self.root / "empty.scn"

    def generate(self, **kwargs):
        return generate_scene(self.upstream, ROOT / "simulations/scenarios/empty_water.scn",
                              self.profile, kwargs.get("namespace", "rov44"), self.output)

    def test_only_one_robot_no_extra_sensors_or_actuator_endpoint(self):
        evidence = self.generate()
        root = ET.parse(self.output).getroot()
        self.assertEqual(len(root.findall("robot")), 1)
        self.assertEqual(root.findall("static"), [])
        self.assertEqual(root.findall("include"), [])
        self.assertEqual(root.findall(".//ros_subscriber"), [])
        self.assertEqual({x.get("name") for x in root.findall("robot/sensor")},
                         {"odometry", "imu_filter", "camera_left", "camera_right"})
        self.assertEqual(root.find("robot/ros_base_link_transforms").get("publish"), "false")
        self.assertEqual(evidence["entities"], ["rov44"])
        self.assertEqual(evidence["assets_sha256"]["robot.obj"],
                         hashlib.sha256((self.upstream / "data/robot.obj").read_bytes()).hexdigest())

    def test_topics_relative_and_substitutions_resolved(self):
        self.generate()
        self.assertNotIn("$(", self.output.read_text())
        for publisher in ET.parse(self.output).findall(".//ros_publisher"):
            self.assertFalse(publisher.get("topic").startswith("/"))

    def test_modified_upstream_fails(self):
        self.source.write_text(self.source.read_text()+"\n")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.generate()

    def test_missing_asset_fails(self):
        (self.upstream / "data/robot.obj").unlink()
        with self.assertRaisesRegex(ValueError, "Missing upstream asset"):
            self.generate()

    def test_actuator_order_change_fails(self):
        self.profile["thruster_order"] = list(reversed(self.profile["thruster_order"]))
        with self.assertRaisesRegex(ValueError, "thruster order"):
            self.generate()

    def test_modified_asset_rejected_against_build_manifest(self):
        expected = {"robot.obj": hashlib.sha256((self.upstream / "data/robot.obj").read_bytes()).hexdigest()}
        (self.upstream / "data/robot.obj").write_text("modified mesh")
        with self.assertRaisesRegex(ValueError, "Asset hash mismatch"):
            generate_scene(self.upstream, ROOT / "simulations/scenarios/empty_water.scn",
                           self.profile, "rov44", self.output, expected_assets=expected)

    def test_namespace_injection_fails(self):
        with self.assertRaises(ValueError):
            self.generate(namespace="../not_a_robot")

    def test_asset_path_escape_fails(self):
        root = ET.parse(self.source)
        root.find(".//mesh").set("filename", "../outside.obj")
        root.write(self.source)
        self.profile["upstream_scene_sha256"] = hashlib.sha256(self.source.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, "escapes"):
            self.generate()
