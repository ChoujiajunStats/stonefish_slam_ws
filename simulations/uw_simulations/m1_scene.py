"""Explicit M1 derivation. M0 generator remains without any actuator subscription."""
import hashlib,json,math
from pathlib import Path
import xml.etree.ElementTree as ET
import yaml
from uw_simulations.scene import generate_scene,sha256
from uw_robot.frames import qmul,rpy_quaternion,Q_ENU_NED,Q_FRD_FLU
from uw_robot.thrusters import extract_profile,load_profile


def generate_m1_scene(upstream,template,profile,namespace,output,assets,config,session,mapping):
    expected=load_profile(mapping)
    actual=extract_profile(Path(upstream)/'scenarios/bluerov2.scn')
    variant=profile.get('actuator_profile') is not None
    if actual['source_sha256']!=expected['source_sha256'] or (not variant and actual!=expected):
        raise ValueError('Thruster mapping differs from locked source')
    if variant and expected.get('variant')!=config['robot_profile']:raise ValueError('Actuator variant mismatch')
    evidence=generate_scene(upstream,template,profile,namespace,output,expected_assets=assets,actuator_profile=expected if variant else None)
    tree=ET.parse(output);robot=tree.find('robot')
    if config['fixed_fixture']:robot.set('fixed','true')
    q=rpy_quaternion(*[math.radians(x) for x in config['initial_rpy_enu_deg']])
    q=qmul(qmul(Q_ENU_NED,q),Q_FRD_FLU)
    x,y,z,w=q
    native=[math.atan2(2*(w*x+y*z),1-2*(x*x+y*y)),math.asin(max(-1,min(1,2*(w*y-z*x)))),math.atan2(2*(w*z+x*y),1-2*(y*y+z*z))]
    robot.find('world_transform').set('rpy',' '.join(str(v) for v in native))
    ET.SubElement(robot,'uw_terminal',run=Path(output).parent.name,secret=session['terminal_secret'],
                  fixture='true' if config['case_id']!='manual' else 'false',expected_thrusters=str(len(expected['thrusters'])))
    ET.SubElement(robot,'ros_publisher',thrusters='sim/actuators/native_feedback')
    ET.indent(tree,space='  ');tree.write(output,encoding='utf-8',xml_declaration=True)
    evidence.update(scene_sha256=sha256(output),terminal_enabled=True,fixed_fixture=config['fixed_fixture'],
                    initial_rpy_enu_deg=config['initial_rpy_enu_deg'],mapping_sha256=sha256(mapping))
    Path(output).with_suffix('.assets.json').write_text(json.dumps(evidence,indent=2)+'\n')
    return evidence
