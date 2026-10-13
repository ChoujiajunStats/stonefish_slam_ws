"""Robot-owned profile selection and explicit actuator variants; no ROS dependency."""
import copy
from pathlib import Path
import xml.etree.ElementTree as ET
import yaml

PROFILES = {'bluerov2_heavy': 'thrusters_m1.yaml',
            'bluerov2_six_disaware': 'thrusters_six_disaware.yaml'}


def require_profile(name):
    if name not in PROFILES:
        raise ValueError(f'Unknown robot profile: {name}')
    return name


def load_robot(config_dir, name):
    require_profile(name)
    directory = Path(config_dir)
    profile = yaml.safe_load((directory / 'bluerov2_heavy.yaml').read_text())
    if name != 'bluerov2_heavy':
        variant = yaml.safe_load((directory / (name + '.yaml')).read_text())
        if variant['base_profile'] != 'bluerov2_heavy' or variant['actuator_profile'] != PROFILES[name]:
            raise ValueError('Invalid robot variant base/mapping')
        profile.update(variant)
    return profile


def apply_actuators(robot, mapping):
    """Derive native v1.3 XML from an explicit model, preserving the complete hull."""
    original = [a for a in robot.findall('actuator') if a.get('type') == 'thruster']
    templates = {a.get('name'): a for a in original}
    for actuator in original:
        robot.remove(actuator)
    for item in mapping['thrusters']:
        a = copy.deepcopy(templates.get(item['name'], templates['DiveFrontRight']))
        a.set('name', item['name'])
        a.find('origin').set('xyz', ' '.join(map(str, item['position_frd'])))
        a.find('origin').set('rpy', ' '.join(map(str, item['rpy_frd'])))
        specs = a.find('specs')
        specs.attrib.clear()
        specs.attrib.update(max_rpm=str(item['max_rpm']), thrust_coeff=str(item['kt_forward']),
                            thrust_coeff_backward=str(item['kt_reverse']), torque_coeff=str(item['kq']),
                            inverted=str(item['inverted']).lower(),
                            first_order_time_constant=str(item['rotor_time_constant_sec']))
        prop = a.find('propeller')
        prop.set('diameter', str(item['diameter_m']))
        prop.set('right', str(item['right_handed']).lower())
        prop.find('mesh').set('filename', item['propeller_mesh'])
        robot.append(a)
