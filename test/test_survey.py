import math,tempfile,unittest
from pathlib import Path
import yaml
from uw_app.m3_config import load_config
from uw_navigation.survey import Follower
ROOT=Path(__file__).resolve().parents[1]


class SurveyContracts(unittest.TestCase):
    def test_optical_fixture_preserves_body_and_motor_contract(self):
        import xml.etree.ElementTree as ET
        import hashlib
        from uw_simulations.optics import apply_optics
        root=ET.fromstring('<scenario><environment><ocean><water density="1025" jerlov="0.05"/></ocean></environment><robot><base_link name="body"/><actuator name="motor" type="thruster"/></robot><light name="porth_fixed_flood_1"/></scenario>')
        before=ET.tostring(root.find('robot/actuator'));rig=dict(jerlov=.22,lighting='robot_spots',native_flux_each=20000)
        result=apply_optics(root,rig,'test')
        self.assertEqual(root.find('environment/ocean/water').get('density'),'1025')
        self.assertEqual(before,ET.tostring(root.find('robot/actuator')))
        self.assertEqual(len(root.findall('robot/light')),2);self.assertEqual(root.findall('light'),[])
        self.assertEqual(root.findall('.//ros_subscriber'),[])
        for lamp in root.findall('robot/light'):self.assertEqual(lamp.find('link').get('name'),'body')
        self.assertFalse(result['calibrated_real_water'])
        for value in (float('nan'),float('inf'),-1,2):
            with self.assertRaises(ValueError):apply_optics(root,dict(rig,jerlov=value),'test')
        lock=yaml.safe_load((ROOT/'vendor/source-lock.survey.yaml').read_text())
        self.assertEqual(hashlib.sha256((ROOT/'vendor/patches'/lock['patch']).read_bytes()).hexdigest(),lock['patch_sha256'])

    def test_steep_route_keeps_velocity_direction(self):
        f=Follower([[i*.12,0.,i*.16] for i in range(20)],headings=[0.]*20)
        u,_=f.update([0,0,0],[0,0,0,1])
        self.assertAlmostEqual(u[2]/u[0],4/3);self.assertAlmostEqual(u[2],.08)

    def test_long_truth_capture_requires_explicit_profile(self):
        base=yaml.safe_load((ROOT/'config/run.porth.yaml').read_text())
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'config.yaml'
            def validate(c):path.write_text(yaml.safe_dump(c));return load_config(path)
            invalid=dict(base,duration_sec=4000)
            with self.assertRaises(ValueError):validate(invalid)
            survey=dict(base,survey_profile='known_route_capture_v1',survey_plan='porth-survey-v2',survey_plan_sha256='a'*64,
                control_state_source='ground_truth_debug',survey_max_distance_m=600,duration_sec=4000)
            self.assertFalse(validate(survey)['execute_path'])
            for key,value in [('control_state_source','openvins'),('recording_profile','debug'),('survey_plan','../escape'),
                              ('survey_plan_sha256','invalid'),('survey_water_jerlov',float('nan')),('survey_water_jerlov',1.01),('execute_path',True),('duration_sec',8000),('survey_max_distance_m',float('nan'))]:
                bad=dict(survey);bad[key]=value
                with self.assertRaises(ValueError):validate(bad)
            survey.update(execute_path=True,evaluation_phase='diagnostic');self.assertTrue(validate(survey)['execute_path'])
    def test_body_coordinates_turn_before_translation_and_finite_progress(self):
        f=Follower([[i*.15,0,0] for i in range(101)])
        command,p=f.update([0,0,0],[0,0,1,0])
        self.assertAlmostEqual(sum(abs(x) for x in command[:3]),0);self.assertGreater(abs(command[3]),.1)
        q=[0,0,0,1]
        for i in range(101):
            command,p=f.update([i*.15,0,0],q)
            self.assertLessEqual(math.hypot(*command[:2]),.2+1e-8)
            self.assertLessEqual(abs(command[2]),.08);self.assertLessEqual(abs(command[3]),.18)
        self.assertTrue(p['complete']);self.assertGreater(p['progress_m'],14)
        f=Follower([[0,i*.15,0] for i in range(20)])
        command,_=f.update([0,0,0],[0,0,math.sin(math.pi/4),math.cos(math.pi/4)])
        self.assertGreater(command[0],.1);self.assertAlmostEqual(command[1],0,places=8)
    def test_retained_view_reversal_reaches_both_ends(self):
        points=[[i*.15,0.,0.] for i in range(31)]+[[4.5,0.,0.]]+[[i*.15,0.,0.] for i in range(29,-1,-1)]
        f=Follower(points,headings=[0.]*len(points));position=[0.,0.,0.];maximum=0.;reverse=False
        for _ in range(2000):
            command,state=f.update(position,[0.,0.,0.,1.])
            reverse=reverse or command[0]<-.1
            position=[x+.05*v for x,v in zip(position,command)];maximum=max(maximum,position[0])
            if state['complete']:break
        self.assertTrue(state['complete']);self.assertTrue(reverse);self.assertGreater(maximum,4.39)
        self.assertLess(position[0],.18)
        with self.assertRaises(ValueError):Follower(points,headings=[0.])

    def test_truth_routing_cannot_apply_to_old_m3(self):
        old=load_config(ROOT/'config/run.m3.yaml');self.assertNotIn('control_state_source',old)
        scene=(ROOT/'app/launch/estimate.launch.py').read_text()
        self.assertIn("milestone==2 or survey",scene)
        guard=(ROOT/'guard/uw_guard/node.py').read_text()
        self.assertIn("self.config.get('scene_profile')=='porth_sump9'",guard)
