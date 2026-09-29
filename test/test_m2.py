import hashlib,math,tempfile,unittest
from pathlib import Path
import yaml
from uw_perception.contracts import ExactPairs,intrinsics,valid_imu
from uw_app.m2_config import load_config
from uw_simulations.m2_scene import write_stereo_calibration
ROOT=Path(__file__).resolve().parents[1]


class M2Contracts(unittest.TestCase):
    def test_exact_pair_never_matches_different_acquisitions(self):
        p=ExactPairs(2)
        self.assertIsNone(p.add(0,100,'l1'));self.assertIsNone(p.add(1,101,'r2'))
        self.assertEqual(p.add(0,101,'l2'),('l2','r2'))
        self.assertIsNone(p.add(1,100,'old'));self.assertIsNone(p.add(0,101,'replay'))
        for stamp in range(102,110):self.assertIsNone(p.add(0,stamp,str(stamp)))
        self.assertEqual(len(p.pending[0]),2);self.assertGreater(p.dropped,0)
    def test_projection_uses_pixel_centres_and_metric_baseline(self):
        fx,fy,cx,cy=intrinsics(640,480,75)
        self.assertAlmostEqual(fx,640/(2*math.tan(math.radians(37.5))))
        self.assertEqual((cx,cy),(319.5,239.5));self.assertEqual(fx,fy)
        profile=yaml.safe_load((ROOT/'robot/config/bluerov2_heavy.yaml').read_text())
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'stereo.yaml';write_stereo_calibration(profile,path)
            p=yaml.safe_load(path.read_text().split('\n',1)[1])
        left=p['cam0']['T_cam_imu'];right=p['cam1']['T_cam_imu']
        self.assertAlmostEqual(left[0][3]-right[0][3],.145)
        self.assertEqual([r[:3] for r in left[:3]],[[0,-1,0],[0,0,-1],[1,0,0]])
        self.assertEqual(left[1][3],-.15);self.assertEqual(left[2][3],-.16)
    def test_imu_rejects_truth_orientation_nonfinite_wrong_frame(self):
        self.assertTrue(valid_imu([0,0,-9.81],[0,0,0],[-1]+[0]*8,'rov/imu_filter','rov/imu_filter'))
        for a,c,f in [([math.nan,0,0],[-1]*9,'imu'),([0,0,9.81],[0]*9,'imu'),([0,0,9.81],[-1]*9,'wrong')]:
            self.assertFalse(valid_imu(a,[0,0,0],c,f,'imu'))
    def test_m2_is_explicit_and_manual_never_autoarms(self):
        cfg=load_config(ROOT/'config/run.m2.yaml');self.assertFalse(cfg['diagnostic_motion']);self.assertFalse(cfg['fixed_fixture'])
        with self.assertRaises(ValueError):load_config(ROOT/'config/run.m1.yaml')
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'config.yaml';cfg['diagnostic_motion']=True;p.write_text(yaml.safe_dump(cfg))
            with self.assertRaises(ValueError):load_config(p)
    def test_additive_patches_locked_parent_unmodified(self):
        p=yaml.safe_load((ROOT/'vendor/source-lock.m2.yaml').read_text())
        self.assertEqual(p['parent_source_lock_sha256'],hashlib.sha256((ROOT/'vendor/source-lock.yaml').read_bytes()).hexdigest())
        for patch in p['additive_patches']:self.assertEqual(patch['sha256'],hashlib.sha256((ROOT/'vendor'/patch['path']).read_bytes()).hexdigest())
        self.assertEqual(p['open_vins']['commit'],'93adc241390d13e99232652cf05cbe18a93c7bea')

    def test_generated_calibration_is_accepted_by_native_opencv_parser(self):
        try:import cv2
        except ImportError:self.skipTest('OpenCV remains inside the image')
        profile=yaml.safe_load((ROOT/'robot/config/bluerov2_heavy.yaml').read_text())
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'stereo.yaml';write_stereo_calibration(profile,path)
            fs=cv2.FileStorage(str(path),cv2.FILE_STORAGE_READ)
            self.assertTrue(fs.isOpened())
            self.assertEqual(fs.getNode('cam0').getNode('T_cam_imu').size(),4)
            self.assertAlmostEqual(fs.getNode('cam0').getNode('T_cam_imu').at(0).at(3).real(),.0725)
            fs.release()

    def test_evaluation_removes_only_initial_yaw_translation_not_scale(self):
        try:import numpy as np
        except ImportError:self.skipTest('NumPy remains inside the image')
        from uw_benchmark.m2_metrics import evaluate
        truth=[dict(stamp=i*.1,position=[i*.01,0.,-2.],velocity=[.1,0.,0.],quaternion=[0.,0.,0.,1.]) for i in range(100)]
        estimate=[dict(r,position=[5.,-3.-r['position'][0],1.],quaternion=[0.,0.,-math.sqrt(.5),math.sqrt(.5)]) for r in truth]
        m,_=evaluate(truth,estimate);self.assertLess(m['position_rmse_m'],1e-12)
        doubled=[dict(r,position=[5.,-3.-2*truth[i]['position'][0],1.]) for i,r in enumerate(estimate)]
        m,_=evaluate(truth,doubled);self.assertGreater(m['position_rmse_m'],.5)
        rewind=truth[:50]+[dict(r,stamp=r['stamp']-2) for r in truth[50:]]
        self.assertEqual(evaluate(rewind,estimate),({},None))
