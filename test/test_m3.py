import math,tempfile,unittest
from pathlib import Path
import yaml
from uw_navigation.core import guide,body_error,wrap,validate_waypoints,relative_goal
from uw_app.m3_config import load_config
ROOT=Path(__file__).resolve().parents[1]


class M3Contracts(unittest.TestCase):
    def test_frame_rotation_not_just_frame_label(self):
        error,d=body_error([0,0,0],[0,0,math.sin(math.pi/4),math.cos(math.pi/4)],[0,1,0])
        self.assertAlmostEqual(error[0],1);self.assertAlmostEqual(error[1],0);self.assertEqual(d,1)
        error,_=body_error([0,0,0],[0,math.sin(math.pi/8),0,math.cos(math.pi/8)],[0,0,1])
        self.assertAlmostEqual(error[0],-math.sqrt(.5));self.assertAlmostEqual(error[2],math.sqrt(.5))
    def test_relative_mission_resolves_numeric_coordinates(self):
        xyz,angle=relative_goal([1,0,.2],.2,[3,4,5],math.pi/2)
        self.assertAlmostEqual(xyz[0],3);self.assertAlmostEqual(xyz[1],5);self.assertAlmostEqual(xyz[2],5.2);self.assertAlmostEqual(angle,math.pi/2+.2)
    def test_guidance_bounds_and_short_yaw_path(self):
        p=yaml.safe_load((ROOT/'navigation/config/defaults.yaml').read_text())
        v,d,a=guide([0,0,0],[0,0,math.sin(1.55),math.cos(1.55)],[1,1,1],-3.1,p)
        self.assertLessEqual(math.hypot(*v[:2]),p['horizontal_speed_m_s']+1e-12);self.assertEqual(v[2],p['vertical_speed_m_s'])
        self.assertGreater(a,0);self.assertLess(a,.1)
        with self.assertRaises(ValueError):body_error([math.nan,0,0],[0,0,0,1],[0,0,0])
    def test_mission_contract_requires_explicit_authority_and_local_goals(self):
        p=yaml.safe_load((ROOT/'tasks/config/defaults.yaml').read_text());points=[('r/odom',[.4,0,0],[0,0,0,1])]
        self.assertIsNone(validate_waypoints('run','run','mission',True,points,20,'r/odom',p))
        for run,arm,pt,timeout in [('old',True,points,20),('run',False,points,20),('run',True,[],20),('run',True,points,math.inf),('run',True,[('world',[0,0,0],[0,0,0,1])],20),('run',True,[('r/odom',[2,0,0],[0,0,0,1])],20)]:
            self.assertIsNotNone(validate_waypoints(run,'run','m',arm,pt,timeout,'r/odom',p))
    def test_explicit_schema_no_truth_or_fixed_body_fallback(self):
        c=load_config(ROOT/'config/run.m3.yaml');self.assertEqual(c['schema_version'],4)
        with self.assertRaises(ValueError):load_config(ROOT/'config/run.m2.yaml')
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.yaml'
            for key,val in [('fixed_fixture',True),('diagnostic_motion',True),('state_source','ground_truth_debug'),('navigation_profile','magic')]:
                bad=dict(c);bad[key]=val;p.write_text(yaml.safe_dump(bad))
                with self.assertRaises(ValueError):load_config(p)
    def test_navigation_has_no_motor_or_truth_dependencies(self):
        for directory in ('navigation','tasks'):
            for p in (ROOT/directory).rglob('*.py'):
                text=p.read_text();self.assertNotIn('sim/ground_truth/odometry',text);self.assertNotIn('ActuatorOutput',text);self.assertNotIn('Thruster',text)
        code=(ROOT/'navigation/uw_navigation/node.py').read_text()
        self.assertIn('issued_steady_ns=g.issued_steady_ns,valid_until_steady_ns=g.deadline_steady_ns',code)
        self.assertIn('now<g.deadline_steady_ns',code)

    def test_absolute_intent_deadline_never_forges_issue_time(self):
        from uw_guard.contracts import validate_request
        request=dict(run_id='r',source='navigation',token='t',generation=1,sequence=1,issued_ns=1000000000,
            stamp_ns=2000000000,frame='base',expected_frame='base',twist=[0]*6,names=[],setpoint=[])
        args=(1010000000,2000000000,'r','navigation','t',1,0,'body_velocity',[],[.4,.4,.2,.4])
        self.assertIsNone(validate_request(request,*args))
        request['valid_until_ns']=1010000000
        self.assertEqual(validate_request(request,*args),'expired_intent_deadline')
        request['valid_until_ns']=1020000000
        self.assertIsNone(validate_request(request,*args))
        self.assertEqual(request['issued_ns'],1000000000)
