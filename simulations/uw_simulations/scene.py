"""Derive one inspect-only robot from a verified upstream scene at runtime."""

import copy
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def generate_scene(upstream_share, template, profile, namespace, output, expected_assets=None):
    if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]{0,47}", namespace):
        raise ValueError("Invalid namespace")
    upstream_share = Path(upstream_share)
    source = upstream_share / "scenarios/bluerov2.scn"
    if sha256(source) != profile["upstream_scene_sha256"]:
        raise ValueError("Upstream robot scenario hash mismatch")
    source_root = ET.parse(source).getroot()
    root = ET.parse(template).getroot()
    if root.findall("robot") or root.findall("static") or root.findall("include"):
        raise ValueError("Empty-water template must not contain entities or includes")
    for look in source_root.findall("looks/look"):
        root.find("looks").append(copy.deepcopy(look))
    robot = copy.deepcopy(source_root.find("robot"))
    robot.set("name", namespace)
    robot.find("world_transform").set("xyz", "0 0 2")
    robot.find("world_transform").set("rpy", "0 0 0")
    # No motor subscriber exists in M0, including the raw upstream topic.
    for element in list(robot):
        if element.tag in ("ros_subscriber", "ros_publisher", "ros_base_link_transforms"):
            robot.remove(element)
        if element.tag == "sensor" and element.get("name") not in (
                "odometry", "imu_filter", "camera_left", "camera_right"):
            robot.remove(element)
    ET.SubElement(robot, "ros_base_link_transforms", publish="false")
    for sensor in robot.findall("sensor"):
        name = sensor.get("name")
        topic = {"odometry": "odometry_ned", "imu_filter": "imu_frd",
                 "camera_left": "left", "camera_right": "right"}[name]
        sensor.find("ros_publisher").set("topic", f"sim/raw/{topic}")
        if name.startswith("camera_"):
            side = name.split("_")[1]
            camera = profile["cameras"][side]
            sensor.find("origin").set("xyz", " ".join(map(str, camera["xyz_frd"])))
            sensor.find("origin").set("rpy", " ".join(map(str, camera["rpy_frd"])))
            specs = sensor.find("specs")
            specs.attrib.clear()
            specs.attrib.update(resolution_x=str(camera["width"]),
                                resolution_y=str(camera["height"]),
                                horizontal_fov=str(camera["horizontal_fov_deg"]))
    root.append(robot)
    assets = {}
    for element in root.iter():
        for key in ("filename", "texture"):
            if key in element.attrib:
                ref = element.get(key)
                asset = (upstream_share / "data" / ref).resolve()
                if not asset.is_relative_to((upstream_share / "data").resolve()):
                    raise ValueError(f"Asset escapes upstream data directory: {ref}")
                if not asset.is_file():
                    raise ValueError(f"Missing upstream asset: {ref}")
                assets[ref] = sha256(asset)
                if expected_assets is not None and assets[ref] != expected_assets.get(ref):
                    raise ValueError(f"Asset hash mismatch against image build: {ref}")
    expected_order = profile["thruster_order"]
    actual = [x.get("name") for x in robot.findall("actuator") if x.get("type") == "thruster"]
    if actual != expected_order:
        raise ValueError(f"Unexpected thruster order: {actual}")
    output = Path(output)
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(output, encoding="utf-8", xml_declaration=True)
    if "$(" in output.read_text():
        raise ValueError("Unresolved upstream scenario substitution")
    evidence = {"upstream_scene_sha256": sha256(source), "scene_sha256": sha256(output),
                "assets_sha256": assets, "actuator_subscribers": 0,
                "entities": [namespace], "spawn_ned_m": [0, 0, 2]}
    output.with_suffix(".assets.json").write_text(json.dumps(evidence, indent=2)+"\n")
    return evidence
