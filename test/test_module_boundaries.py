"""Package ownership and behavior-preserving composition contracts (no ROS needed)."""
import ast
import copy
import json
import math
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

import yaml
from uw_guard.configuration import route_safety_envelope
from uw_localization.orbslam3 import prepare as prepare_orb
from uw_localization.rtabmap import prepare as prepare_rtabmap
from uw_robot.description import isolated_visual_urdf, make_urdf
from uw_robot.frames import quaternion_rpy, rpy_quaternion
from uw_simulations.survey_scene import prepare as prepare_scene
from uw_ui.layouts import estimation_layout

ROOT = Path(__file__).resolve().parents[1]

# Direct implementation dependencies, including launch files. ROS messages are
# shared interfaces; app may assemble packages but they cannot import app.
ALLOWED = {
    'uw_runtime': set(), 'uw_robot': set(), 'uw_interfaces': set(), 'uw_ui': set(),
    'uw_perception': {'uw_robot'},
    'uw_localization': {'uw_perception'},
    'uw_controller': {'uw_robot', 'uw_interfaces'},
    'uw_guard': {'uw_robot', 'uw_interfaces'},
    'uw_simulations': {'uw_robot', 'uw_interfaces', 'uw_perception'},
    'uw_navigation': {'uw_interfaces'},
    'uw_tasks': {'uw_interfaces', 'uw_navigation'},
    'uw_benchmark': {'uw_interfaces', 'uw_runtime', 'uw_robot', 'uw_localization',
                     'uw_navigation', 'uw_perception', 'uw_simulations'},
    'uw_app': {'uw_runtime', 'uw_robot', 'uw_simulations', 'uw_ui', 'uw_guard',
               'uw_localization', 'uw_controller', 'uw_perception', 'uw_navigation',
               'uw_tasks', 'uw_interfaces', 'uw_benchmark'},
}


class ModuleBoundaryTests(unittest.TestCase):
    def test_imports_obey_ownership_and_manifest_including_launch(self):
        manifests = {ET.parse(p).getroot().findtext('name'): p for p in ROOT.glob('*/package.xml')}
        self.assertEqual(set(manifests), set(ALLOWED))
        for name, manifest in manifests.items():
            declared = {x.text for x in ET.parse(manifest).getroot() if x.tag.endswith('depend')}
            self.assertFalse((declared & ALLOWED.keys()) - ALLOWED[name], name)
            sources = list((manifest.parent / name).rglob('*.py'))
            sources += list((manifest.parent / 'launch').glob('*.py'))
            for source in sources:
                for node in ast.walk(ast.parse(source.read_text())):
                    imports = ([node.module] if isinstance(node, ast.ImportFrom) and node.module
                               else [a.name for a in node.names] if isinstance(node, ast.Import) else [])
                    for module in imports:
                        dependency = module.split('.')[0]
                        if dependency.startswith('uw_') and dependency != name:
                            self.assertIn(dependency, ALLOWED[name], str(source))
                            self.assertIn(dependency, declared, str(source))
                        if name == 'uw_app':
                            self.assertFalse(module.startswith(('ctypes', 'xml.etree', 'importlib.util')), str(source))

    def test_native_settings_match_pre_refactor_outputs(self):
        baseline = json.loads((ROOT / 'test/fixtures/composition-baseline.json').read_text())
        profile = yaml.safe_load((ROOT / 'robot/config/bluerov2_heavy.yaml').read_text())
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            params = prepare_orb(out, 'test_robot', profile, ROOT / 'localization/config/orbslam3_stereo.yaml')
            actual = {k: v.replace(directory, '/RUN') if isinstance(v, str) else v for k, v in params.items()}
            self.assertEqual(actual, baseline['orb']['parameters'])
            self.assertEqual((out / 'orbslam3-settings.yaml').read_text(), baseline['orb']['settings'])
            self.assertEqual(json.loads((out / 'orb-contract.json').read_text()), baseline['orb']['contract'])
            for survey in (False, True):
                path = prepare_rtabmap(out, 'test_robot', ROOT / 'localization/config/rtabmap_stereo.yaml', long_survey=survey)
                self.assertEqual(yaml.safe_load(Path(path).read_text().replace(directory, '/RUN')),
                                 baseline['rtabmap'][str(survey)])

    def test_ui_layouts_match_pre_refactor_without_app_or_ros(self):
        baseline = json.loads((ROOT / 'test/fixtures/composition-baseline.json').read_text())
        for key, expected in baseline['layouts'].items():
            stage, porth, survey, orb = key.split('-')
            actual = estimation_layout(ROOT / 'ui/config/inspect.rviz', 'test_robot', milestone=int(stage),
                                       porth=porth == 'True', survey=survey == 'True', orb=orb == 'True',
                                       orb_robot_description=Path('/RUN/orb-robot.urdf'))
            self.assertEqual(actual, expected, key)

    def test_standalone_visual_has_no_cross_gauge_sensor_transforms(self):
        profile = yaml.safe_load((ROOT / 'robot/config/bluerov2_heavy.yaml').read_text())
        original = make_urdf('unit', profile)
        result = ET.fromstring(isolated_visual_urdf(original, 'unit/orb_body'))
        self.assertEqual(len(result), 1)
        self.assertEqual(result.find('link').get('name'), 'unit/orb_body')
        self.assertEqual(ET.tostring(result.find('link/visual')), ET.tostring(ET.fromstring(original).find('link/visual')))
        self.assertGreater(len(ET.fromstring(original).findall('joint')), 0)
        with self.assertRaises(ValueError):
            isolated_visual_urdf('<robot/>', 'unit/orb_body')

    def test_shared_quaternion_conversion_preserves_flu_angles(self):
        for angles in ((0, 0, 0), (.3, -.6, 2.1), (-.4, .8, -2.7), (0, math.pi / 2, 0)):
            actual = quaternion_rpy(rpy_quaternion(*angles))
            for a, b in zip(actual, angles):
                self.assertAlmostEqual(a, b, places=7)

    def test_guard_route_envelope_is_explicit_and_rejects_invalid_data(self):
        route = [[-4, 2, -6], [3, 8, -3]]
        self.assertEqual(route_safety_envelope(route), {'depth_enu_m': [-7, -2], 'horizontal_position_abs_m': 10})
        for invalid in ([], [[1, 2]], [[1, float('nan'), 3]], [[1, 2, float('inf')]]):
            with self.assertRaises(ValueError):
                route_safety_envelope(invalid)

    def test_scene_uses_explicit_plan_and_preserves_dynamics(self):
        xml = ('<scenario><robot><world_transform xyz="0 0 0"/>'
               '<base_link><mass value="42"/></base_link><actuator name="motor"/></robot>'
               '<static name="porth_sump9"><visual><mesh scale="1"/></visual>'
               '<physical><mesh scale="1"/></physical><world_transform xyz="0 0 0"/></static>'
               '<light name="porth_fixed_flood_0"/></scenario>')
        plan = dict(clearance_lower_bound_m=.9, spawn_enu=[2, 3, -4], spawn_yaw_enu_deg=90.,
                    lights_enu=[[5, 6, -7]], scale=3, cave_offset_ned=[1, 2, 3], light_native_illuminance=123)
        original = copy.deepcopy(plan)
        with tempfile.TemporaryDirectory() as directory:
            scene, evidence = Path(directory) / 'scene.xml', Path(directory) / 'assets.json'
            scene.write_text(xml); evidence.write_text('{}')
            with self.assertRaises(ValueError):
                prepare_scene(scene, evidence, plan, plan_sha256='a' * 64, namespace='unit', initial_yaw_enu_deg=0)
            self.assertEqual(scene.read_text(), xml)
            prepare_scene(scene, evidence, plan, plan_sha256='a' * 64, namespace='unit', initial_yaw_enu_deg=90.)
            root = ET.parse(scene).getroot()
            self.assertEqual(root.find('robot/world_transform').get('xyz'), '3 2 4')
            self.assertEqual(root.find('robot/base_link/mass').get('value'), '42')
            self.assertEqual(root.find('robot/actuator').get('name'), 'motor')
            self.assertEqual(root.find('light/world_transform').get('xyz'), '6 5 7')
            self.assertEqual(len(root.findall('light')), 1)
            self.assertEqual(json.loads(evidence.read_text())['survey_plan_sha256'], 'a' * 64)
            self.assertEqual(plan, original)
