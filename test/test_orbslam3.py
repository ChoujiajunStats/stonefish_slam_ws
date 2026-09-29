"""Calibration, scope and patch contracts; live SLAM is verified separately."""
import copy,hashlib,json,math,tempfile,unittest
from pathlib import Path
import yaml
from uw_app.m3_config import load_config
from uw_app.orbslam3 import prepare
ROOT=Path(__file__).resolve().parents[1]


class OrbContracts(unittest.TestCase):
    def test_explicit_profile_preserves_previous_default_and_authority(self):
        self.assertEqual(load_config(ROOT/'config/run.porth-survey.yaml')['slam_profile'],'rtabmap_stereo')
        cfg=load_config(ROOT/'config/run.porth-orbslam3.yaml')
        self.assertFalse(cfg['execute_path']);self.assertEqual(cfg['control_state_source'],'ground_truth_debug')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'request.yaml'
            for changes in [dict(slam_profile='unknown'),dict(control_state_source='openvins'),dict(execute_path=True)]:
                path.write_text(yaml.safe_dump(dict(cfg,**changes)))
                with self.assertRaises(ValueError):load_config(path)
            cfg=yaml.safe_load((ROOT/'config/run.porth.yaml').read_text());cfg['slam_profile']='orbslam3_stereo';path.write_text(yaml.safe_dump(cfg))
            with self.assertRaises(ValueError):load_config(path)

    def test_calibration_and_camera_to_body_lever_arm(self):
        profile=yaml.safe_load((ROOT/'robot/config/bluerov2_heavy.yaml').read_text())
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory);(out/'robot_profile.yaml').write_text(yaml.safe_dump(profile))
            prepare(out,{'namespace':'test_robot'},lambda name:str(ROOT/'localization'))
            c=json.loads((out/'orb-contract.json').read_text());fx,fy,cx,cy=c['intrinsics']
            self.assertAlmostEqual(c['baseline_m'],.145);self.assertAlmostEqual(fx,640/(2*math.tan(math.radians(75)/2)))
            self.assertEqual([cx,cy],[319.5,239.5]);self.assertEqual(fx,fy)
            m=c['T_body_camera']
            # An optical point one metre forward projects one metre forward in FLU.
            result=[m[i*4+2]+m[i*4+3] for i in range(3)]
            self.assertEqual(result,[1.16,.0725,-.15])
            self.assertFalse(c['truth_input']);self.assertFalse(c['external_odometry_input']);self.assertFalse(c['imu_input'])
            profile['cameras']['right']['xyz_frd'][1]=-.0725
            (out/'robot_profile.yaml').write_text(yaml.safe_dump(profile))
            with self.assertRaises(ValueError):prepare(out,{'namespace':'test_robot'},lambda name:str(ROOT/'localization'))

    def test_pinned_sources_and_patch_hashes(self):
        lock=yaml.safe_load((ROOT/'vendor/source-lock.orbslam3.yaml').read_text())
        self.assertEqual(hashlib.sha256((ROOT/'vendor/source-lock.survey.yaml').read_bytes()).hexdigest(),lock['parent_lock_sha256'])
        for repo in lock['repositories']:
            self.assertRegex(repo['commit'],r'^[a-f0-9]{40}$')
            for p in repo['patches']:self.assertEqual(hashlib.sha256((ROOT/'vendor/patches'/p['file']).read_bytes()).hexdigest(),p['sha256'])
