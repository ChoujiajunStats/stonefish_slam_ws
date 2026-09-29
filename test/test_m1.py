import copy,hashlib,math
from pathlib import Path
import unittest
import tempfile
import yaml
from uw_app.m1_config import load_run_config
from uw_app.config import load_config,ConfigError
from uw_guard.contracts import validate_request
ROOT=Path(__file__).resolve().parents[1]


class M1Contracts(unittest.TestCase):
    def setUp(self):
        self.now=1_000_000_000
        self.req=dict(run_id='run',source='benchmark',token='token',generation=2,sequence=3,issued_ns=self.now,
            frame='test/base_link',expected_frame='test/base_link',stamp_ns=2_000_000_000,twist=[0.]*6,names=[],setpoint=[])
    def validate(self,request=None,mode='body_velocity'):
        return validate_request(request or self.req,self.now,2_000_000_000,'run','benchmark','token',2,2,mode,['a','b'],[.4,.4,.2,.4])
    def test_valid_zero_is_a_closed_loop_request(self):self.assertIsNone(self.validate())
    def test_identity_and_generation_fail(self):
        for key,value in [('run_id','old'),('source','cli'),('token','old'),('generation',1),('sequence',2)]:
            with self.subTest(key=key):self.assertIsNotNone(self.validate(dict(self.req,**{key:value})))
    def test_stamp_contract(self):
        for key,value in [('issued_ns',0),('issued_ns',self.now+1),('stamp_ns',1_000_000_000),('stamp_ns',2_060_000_000),('frame','world')]:
            with self.subTest(key=key):self.assertIsNotNone(self.validate(dict(self.req,**{key:value})))
    def test_invalid_and_overlimit_are_distinct(self):
        for value in [float('nan'),float('inf')]:
            r=copy.deepcopy(self.req);r['twist'][0]=value;self.assertEqual(self.validate(r),'nonfinite_twist')
        r=copy.deepcopy(self.req);r['twist'][0]=.41;self.assertEqual(self.validate(r),'request_limit_exceeded')
    def test_roll_pitch_rate_rejected(self):
        for index in (3,4):
            r=copy.deepcopy(self.req);r['twist'][index]=.001;self.assertEqual(self.validate(r),'unsupported_roll_pitch_rate')
    def test_probe_names_and_mode(self):
        r=dict(self.req,names=['a','b'],setpoint=[.1,0.]);self.assertIsNone(self.validate(r,'actuator_probe'))
        self.assertEqual(self.validate(r),'probe_in_velocity_mode')
        for names in (['b','a'],['a','a'],['a'],['a','x']):self.assertEqual(self.validate(dict(r,names=names),'actuator_probe'),'invalid_channels')
    def test_m0_cannot_enable_m1_by_changing_one_field(self):
        self.assertEqual(load_config(ROOT/'config/run.empty_water.example.yaml')['controller_profile'],'disabled')
        with self.assertRaises(ConfigError):load_config(ROOT/'config/run.m1.yaml')
        self.assertEqual(load_run_config(ROOT/'config/run.m1.yaml')['schema_version'],2)
    def test_m0_late_nonzero_exit_is_failure(self):
        from uw_benchmark.artifacts import classify_result
        result=classify_result(0,{'status':'PASS'},[{'name':'rviz','returncode':-11,'before_probe_completion':False}],True,True)
        self.assertEqual(result[0],'FAILED')

    def test_formal_freeze_rejects_between_case_changes(self):
        from uw_benchmark.campaign import verify_freeze
        with tempfile.TemporaryDirectory() as directory:
            repo=Path(directory);source=repo/'controller.py';source.write_text('original')
            freeze={'image_id':'fixed-image','files':{'controller.py':hashlib.sha256(source.read_bytes()).hexdigest()}}
            verify_freeze(repo,freeze,'fixed-image')
            source.write_text('edited after first case')
            with self.assertRaisesRegex(RuntimeError,'Formal freeze differs'):verify_freeze(repo,freeze,'fixed-image')
            with self.assertRaisesRegex(RuntimeError,'Formal image differs'):verify_freeze(repo,freeze,'changed-image')

    def test_dds_unchanged_from_accepted_m0(self):
        self.assertEqual(hashlib.sha256((ROOT/'docker/fastdds.xml').read_bytes()).hexdigest(),
                         'ca6961088346410f2e4770396caecb17ade8848974bfa6b427a31d7d307f53f7')


try:
    import numpy as np
    from uw_robot.thrusters import Allocation,load_profile
    from uw_controller.core import BodyController,rpy
except ImportError:np=None


@unittest.skipIf(np is None,'M1 numerical tests require project container NumPy; no host install')
class M1Allocation(unittest.TestCase):
    def setUp(self):
        self.profile=load_profile(ROOT/'robot/config/thrusters_m1.yaml')
        self.model=dict(names=[t['name'] for t in self.profile['thrusters']],cg_frd_m=[-.00548,-.000092,.07699],
            geometry=[dict(position_frd=t['position_frd'],axis_frd=t['axis_frd']) for t in self.profile['thrusters']])
        self.a=Allocation(self.profile,self.model)
    def test_rank_and_attainable_wrench(self):
        self.assertEqual(np.linalg.matrix_rank(self.a.matrix),6)
        for i in range(6):
            w=np.eye(6)[i];u,actual,sat=self.a.allocate(w)
            np.testing.assert_allclose(actual,w,atol=1e-5);self.assertLessEqual(max(abs(u)),.6)
    def test_infeasible_wrench_is_bounded_and_signs_follow_model(self):
        u,w,sat=self.a.allocate([1000]*6);self.assertTrue(sat);self.assertLessEqual(max(abs(u)),.6+1e-9)
        np.testing.assert_allclose(self.a.native_sign,[-1,-1,-1,-1,1,1,1,1])
    def test_reference_point_shift_has_correct_moment(self):
        shifted=copy.deepcopy(self.model);shifted['cg_frd_m'][0]+=.1;b=Allocation(self.profile,shifted)
        for i in range(8):np.testing.assert_allclose(b.matrix[3:,i]-self.a.matrix[3:,i],np.cross([-.1,0,0],self.a.matrix[:3,i]),atol=1e-9)
    def test_geometry_or_order_mismatch_fails(self):
        m=copy.deepcopy(self.model);m['names'].reverse()
        with self.assertRaises(ValueError):Allocation(self.profile,m)
        m=copy.deepcopy(self.model);m['geometry'][0]['position_frd'][0]+=.1
        with self.assertRaises(ValueError):Allocation(self.profile,m)
    def test_attitude_feedback_acts_with_zero_rates(self):
        c=BodyController(yaml.safe_load((ROOT/'controller/config/defaults.yaml').read_text()),self.a)
        u,w,actual,sat=c.update([0]*4,[0]*6,[.1,-.1,0],.02)
        self.assertLess(w[3],0);self.assertGreater(w[4],0);self.assertGreater(max(abs(u)),0)
    def test_anti_windup_reset_and_bad_dt(self):
        c=BodyController(yaml.safe_load((ROOT/'controller/config/defaults.yaml').read_text()),self.a)
        for _ in range(200):c.update([100]*4,[0]*6,[0]*3,.02)
        self.assertTrue(np.all(np.abs(c.integral)<=c.p['integral_force_limits']))
        c.reset();np.testing.assert_array_equal(c.integral,0);np.testing.assert_array_equal(c.previous,0)
        for dt in (0,-.01,.2,float('nan')):
            with self.assertRaises(ValueError):c.update([0]*4,[0]*6,[0]*3,dt)
