"""Optional Porth scenery. Never alters the locked vehicle hydrodynamics."""
import json, math
from pathlib import Path
import xml.etree.ElementTree as ET
from uw_simulations.scene import sha256


def load_asset(directory):
    directory=Path(directory)
    asset=json.loads((directory/'asset.json').read_text())
    for name,expected in asset['files_sha256'].items():
        path=(directory/name).resolve()
        if not path.is_relative_to(directory.resolve()) or sha256(path)!=expected:
            raise ValueError('Imported asset hash mismatch: '+name)
    if asset['scale']<=0 or asset['route_center_to_collision_surface_lower_bound_m']<=asset['robot_screening_radius_m']:
        raise ValueError('Invalid cave scale or prescribed route clearance')
    return asset


def add_cave(scene,directory,asset):
    directory=Path(directory);tree=ET.parse(scene);root=tree.getroot()
    robot=root.find('robot');x,y,z=asset['spawn_enu']
    robot.find('world_transform').set('xyz',f'{y} {x} {-z}')
    # Optical environment is explicit and separate from mass/buoyancy/drag.
    root.find('environment/ocean/water').set('jerlov','0.05')
    ET.SubElement(root.find('looks'),'look',name='porth_rock',gray='1',roughness='1',texture=str(directory/'albedo.png'))
    cave=ET.SubElement(root,'static',name='porth_sump9',type='model')
    for tag,filename in [('physical','collision.obj'),('visual','visual.obj')]:
        part=ET.SubElement(cave,tag)
        attrs=dict(filename=str(directory/filename),scale=str(asset['scale']))
        if tag=='physical':attrs['convex']='false'
        ET.SubElement(part,'mesh',**attrs);ET.SubElement(part,'origin',xyz='0 0 0',rpy='0 0 0')
    ET.SubElement(cave,'material',name='Neutral');ET.SubElement(cave,'look',name='porth_rock')
    ET.SubElement(cave,'world_transform',xyz=' '.join(map(str,asset['cave_offset_ned'])),rpy=f"0 0 {asset['cave_yaw_ned']}")
    for side in (-1,1):
        # Static diagnostic illumination, not an extra vehicle actuator. The
        # accepted terminal deliberately requires a thruster-only robot.
        lamp=ET.SubElement(root,'light',name=f'porth_fixed_flood_{side}')
        ET.SubElement(lamp,'specs',illuminance='400000',radius='0.03',cone_angle='110')
        ET.SubElement(lamp,'color',temperature='4500')
        ET.SubElement(lamp,'world_transform',xyz=f'0.21 {side*.12} 8',rpy=f'0 {math.pi/2} {side*.05}')
    ET.indent(tree,space='  ');tree.write(scene,encoding='utf-8',xml_declaration=True)
    path=Path(scene).with_suffix('.assets.json');evidence=json.loads(path.read_text())
    evidence.update(scene_sha256=sha256(scene),cave_asset_sha256=sha256(directory/'asset.json'),
        spawn_enu=asset['spawn_enu'],cave_scale=asset['scale'],jerlov=.05,
        lighting={'type':'STATIC_DIAGNOSTIC_FIXTURE','count':2,'illuminance_each':400000,'cone_deg':110,'temperature_k':4500})
    path.write_text(json.dumps(evidence,indent=2)+'\n')
