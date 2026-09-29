"""RViz-only schematic and sensor extrinsics, never a hydrodynamic model."""

import math
import xml.etree.ElementTree as ET
from pathlib import Path

from uw_robot.frames import frd_to_flu


def make_urdf(namespace, profile):
    root = ET.Element("robot", name=namespace)
    base = ET.SubElement(root, "link", name=f"{namespace}/base_link")
    visual = ET.SubElement(base, "visual")
    geometry = ET.SubElement(visual, "geometry")
    ET.SubElement(geometry, "box", size="0.45 0.57 0.25")
    material = ET.SubElement(visual, "material", name="schematic_yellow")
    ET.SubElement(material, "color", rgba="0.95 0.8 0.1 0.65")

    def fixed(child, parent, xyz, rpy):
        ET.SubElement(root, "link", name=f"{namespace}/{child}")
        joint = ET.SubElement(root, "joint", name=f"{child}_fixed", type="fixed")
        ET.SubElement(joint, "parent", link=f"{namespace}/{parent}")
        ET.SubElement(joint, "child", link=f"{namespace}/{child}")
        ET.SubElement(joint, "origin", xyz=" ".join(map(str, xyz)), rpy=" ".join(map(str, rpy)))

    fixed("imu_link", "base_link", (0, 0, 0), (0, 0, 0))
    for side, camera in profile["cameras"].items():
        fixed(f"{side}_camera_link", "base_link", frd_to_flu(camera["xyz_frd"]), (0, 0, 0))
        # Scene and public extrinsics share the exact canonical optical rotation.
        expected = (math.pi/2, 0, math.pi/2)
        if any(abs(a-b) > 1e-10 for a, b in zip(camera["rpy_frd"], expected)):
            raise ValueError("M0 requires aligned canonical stereo optical axes")
        fixed(f"{side}_camera_optical", f"{side}_camera_link", (0, 0, 0), (-math.pi/2, 0, -math.pi/2))
    return ET.tostring(root, encoding="unicode")


def make_mesh_urdf(namespace,profile,asset_directory):
    """Actual locked BlueROV2 visuals; public base frame remains FLU.

    Meshes and thruster origins use native FRD. Rx(pi) converts both geometry
    and translations. These visuals do not affect the Stonefish rigid body.
    """
    directory=Path(asset_directory)/'bluerov2'
    root=ET.fromstring(make_urdf(namespace,profile));base=root.find('link')
    for v in base.findall('visual'):base.remove(v)
    def visual(name,xyz=(0,0,0),angles=(0,0,0)):
        element=ET.SubElement(base,'visual')
        r,p,y=angles
        ET.SubElement(element,'origin',xyz=' '.join(map(str,frd_to_flu(xyz))),rpy=f'{r+math.pi} {-p} {-y}')
        ET.SubElement(ET.SubElement(element,'geometry'),'mesh',filename=(directory/name).as_uri(),scale='1 1 1')
    visual('bluerov2.obj');visual('bluerov2_wings.obj')
    for actuator in ET.parse(directory/'source.scn').getroot().findall('.//actuator'):
        if actuator.get('type')!='thruster':continue
        mesh=actuator.find('propeller/mesh');origin=actuator.find('origin')
        if mesh is not None and origin is not None:
            visual(Path(mesh.get('filename')).name,[float(x) for x in origin.get('xyz').split()],
                [float(x) for x in origin.get('rpy').split()])
    return ET.tostring(root,encoding='unicode')


def isolated_visual_urdf(description, frame):
    """Display one body in an independent SLAM gauge, without sensor TF claims."""
    root = ET.fromstring(description)
    base = root.find('link')
    if base is None:
        raise ValueError('Robot description requires a base link')
    base.set('name', frame)
    for child in list(root):
        if child is not base:
            root.remove(child)
    return ET.tostring(root, encoding='unicode')
