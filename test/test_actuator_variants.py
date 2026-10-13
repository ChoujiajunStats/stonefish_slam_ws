"""Disaware source parity, controllability and unchanged eight-channel defaults."""
import copy
import hashlib
import math
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
import yaml
from uw_robot.profiles import load_robot, apply_actuators
from uw_app.run_config import load_config

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'robot/config'


class VariantContracts(unittest.TestCase):
    def test_explicit_selection_preserves_default_and_cameras(self):
        old = load_robot(CONFIG, 'bluerov2_heavy')
        new = load_robot(CONFIG, 'bluerov2_six_disaware')
        self.assertEqual(len(old['thruster_order']), 8)
        self.assertEqual(len(new['thruster_order']), 6)
        self.assertEqual(old['cameras'], new['cameras'])
        self.assertNotIn('actuator_profile', old)
        self.assertEqual(load_config(ROOT/'config/run.m1.six.yaml')['robot_profile'], 'bluerov2_six_disaware')
        with self.assertRaises(ValueError):load_robot(CONFIG, '../invalid')
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'run.yaml';v=yaml.safe_load((ROOT/'config/run.empty_water.example.yaml').read_text())
            v['robot_profile']='bluerov2_six_disaware';p.write_text(yaml.safe_dump(v))
            with self.assertRaises(ValueError):load_config(p)

    def test_external_adapter_accepts_only_selected_complete_channels(self):
        from uw_simulations.actuator_contract import valid_channels
        for count in (6,8):
            names=[str(i) for i in range(count)]
            self.assertTrue(valid_channels(names,[.12]*count,names))
            for given,values in [(names[:-1],[0.]*(count-1)),(names,[0.]*(14-count)),(list(reversed(names)),[0.]*count),([names[0]]*count,[0.]*count),(names,[float('nan')]*count),(names,[.61]*count)]:
                self.assertFalse(valid_channels(given,values,names))

    def test_six_protocol_reuses_all_baseline_thresholds(self):
        from uw_benchmark.protocols import control_protocol
        old=control_protocol(ROOT,'bluerov2_heavy');new=control_protocol(ROOT,'bluerov2_six_disaware')
        self.assertEqual(set(old['cases'])-set(new['cases']),{'probe_6','probe_7'})
        for name,case in new['cases'].items():self.assertEqual(case,old['cases'][name])

    def test_model_matches_recovered_actuators(self):
        mapping=yaml.safe_load((CONFIG/'thrusters_six_disaware.yaml').read_text())
        source=ET.parse(CONFIG/'disaware-actuators.xml').getroot()
        self.assertEqual([a.get('name') for a in source], [t['name'] for t in mapping['thrusters']])
        for a,t in zip(source,mapping['thrusters']):
            self.assertEqual(list(map(float,a.find('origin').get('xyz').split())),t['position_frd'])
            self.assertEqual(list(map(float,a.find('origin').get('rpy').split())),t['rpy_frd'])
            self.assertEqual(a.find('specs').get('inverted_setpoint')=='true',t['inverted'])
            self.assertEqual(a.find('propeller').get('right')=='true',t['right_handed'])
            self.assertAlmostEqual(float(a.find('specs').get('max_setpoint')),t['max_rpm']*2*math.pi/60)
            self.assertEqual(float(a.find('rotor_dynamics/time_constant').get('value')),t['rotor_time_constant_sec'])
            for name in ('forward','reverse'):
                self.assertEqual(float(a.find('thrust_model/thrust_coeff').get(name)),t['kt_'+name])
            self.assertEqual(float(a.find('thrust_model/torque_coeff').get('value')),t['kq'])
        self.assertEqual(mapping['controlled_axes'],[0,1,2,3,5])
        self.assertEqual(mapping['density_kg_m3'],1025.)

    def test_derivation_preserves_hull_and_only_replaces_motors(self):
        robot=ET.Element('robot');hull=ET.SubElement(robot,'base_link',name='body',mass='11.189')
        ET.SubElement(hull,'inertia',xyz='1 2 3');ET.SubElement(robot,'sensor',name='imu')
        ET.SubElement(robot,'actuator',type='light',name='lamp')
        a=ET.SubElement(robot,'actuator',type='thruster',name='DiveFrontRight')
        ET.SubElement(a,'origin');ET.SubElement(a,'specs');p=ET.SubElement(a,'propeller');ET.SubElement(p,'mesh')
        before=ET.tostring(hull)
        mapping=yaml.safe_load((CONFIG/'thrusters_six_disaware.yaml').read_text())
        apply_actuators(robot,mapping)
        self.assertEqual(ET.tostring(robot.find('base_link')),before)
        self.assertEqual(len(robot.findall('actuator')),7)
        self.assertEqual(len(robot.findall('sensor')),1)
        for a in robot.findall("actuator[@type='thruster']"):
            self.assertEqual(a.find('specs').get('first_order_time_constant'),'0.1')

    def test_native_patch_hashes_and_parent_chain(self):
        lock=yaml.safe_load((ROOT/'vendor/source-lock.actuators.yaml').read_text())
        self.assertEqual(lock['parent_lock_sha256'],hashlib.sha256((ROOT/'vendor/source-lock.orbslam3.yaml').read_bytes()).hexdigest())
        for entry in lock['repositories']:
            self.assertEqual(entry['sha256'],hashlib.sha256((ROOT/'vendor/patches'/entry['patch']).read_bytes()).hexdigest())

try:
    import numpy as np
    from uw_robot.thrusters import Allocation,load_profile
    from uw_controller.core import BodyController
except ImportError:np=None


@unittest.skipIf(np is None,'Container NumPy required; host unchanged')
class SixAllocation(unittest.TestCase):
    def setUp(self):
        self.p=load_profile(CONFIG/'thrusters_six_disaware.yaml')
        self.model=dict(names=[t['name'] for t in self.p['thrusters']],cg_frd_m=[-.0054789746,-.0000924473,.0769923863],
            geometry=[dict(position_frd=t['position_frd'],axis_frd=t['axis_frd']) for t in self.p['thrusters']])
        self.a=Allocation(self.p,self.model)

    def test_five_controlled_axes_are_attainable_with_physical_moment(self):
        self.assertEqual(self.a.matrix.shape,(6,6))
        self.assertEqual(np.linalg.matrix_rank(self.a.control_matrix),5)
        for axis in self.a.controlled_axes:
            w=np.eye(6)[axis];u,predicted,_=self.a.allocate(w)
            np.testing.assert_allclose(predicted[self.a.controlled_axes],w[self.a.controlled_axes],atol=1e-5)
            self.assertLessEqual(max(abs(u)),self.p['setpoint_limit'])
            np.testing.assert_allclose(self.a.predict(u),predicted,atol=1e-9)
        # The full predicted pitch torque is retained as a coupled physical output.
        np.testing.assert_allclose(self.a.native_sign,[-1,-1,-1,-1,1,1])

    def test_unactuated_pitch_never_accumulates_integral(self):
        c=BodyController(yaml.safe_load((ROOT/'controller/config/defaults.yaml').read_text()),self.a)
        for _ in range(500):
            u,w,_,_=c.update([0]*4,[0,0,0,0,.1,0],[0,.1,0],.02)
            self.assertEqual(w[4],0);self.assertEqual(c.attitude_integral[1],0)
        self.assertEqual(len(u),6);c.reset();np.testing.assert_array_equal(c.previous,[0]*6)

    def test_wrong_order_nonfinite_geometry_and_bad_rank_fail_closed(self):
        for key in ('order','nan','rank'):
            model=copy.deepcopy(self.model);profile=copy.deepcopy(self.p)
            if key=='order':model['names'].reverse()
            if key=='nan':model['geometry'][0]['position_frd'][0]=float('nan')
            if key=='rank':
                for i,t in enumerate(profile['thrusters']):
                    t['axis_frd']=[1.,0.,0.];model['geometry'][i]['axis_frd']=[1.,0.,0.]
            with self.assertRaises(ValueError):Allocation(profile,model)
