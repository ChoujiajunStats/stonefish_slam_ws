import json,math,tempfile,unittest
from pathlib import Path
import xml.etree.ElementTree as ET
import yaml
from uw_app.m3_config import load_config
from uw_robot.description import make_urdf,make_mesh_urdf
ROOT=Path(__file__).resolve().parents[1]


class PorthContracts(unittest.TestCase):
    def test_explicit_scene_and_authorization(self):
        old=load_config(ROOT/'config/run.m3.yaml');self.assertNotIn('execute_path',old)
        cfg=load_config(ROOT/'config/run.porth.yaml');self.assertFalse(cfg['execute_path'])
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'cfg.yaml'
            for key,value in [('execute_path','yes'),('execute_path',True),('cave_asset','../other'),('slam_profile','truth'),('initial_rpy_enu_deg',[0,0,0])]:
                bad=dict(cfg);bad[key]=value;p.write_text(yaml.safe_dump(bad))
                with self.assertRaises(ValueError):load_config(p)
            cfg.update(execute_path=True,evaluation_phase='diagnostic');p.write_text(yaml.safe_dump(cfg));self.assertTrue(load_config(p)['execute_path'])
    def test_native_mesh_transform_keeps_sensor_extrinsics(self):
        profile=yaml.safe_load((ROOT/'robot/config/bluerov2_heavy.yaml').read_text())
        with tempfile.TemporaryDirectory() as d:
            robot=Path(d)/'bluerov2';robot.mkdir()
            (robot/'source.scn').write_text('<scenario><robot><actuator type="thruster"><origin xyz="1 2 3" rpy="0.1 0.2 0.3"/><propeller><mesh filename="x/cw.obj"/></propeller></actuator></robot></scenario>')
            before=ET.fromstring(make_urdf('test',profile));after=ET.fromstring(make_mesh_urdf('test',profile,d))
            self.assertEqual([ET.tostring(x) for x in before.findall('joint')],[ET.tostring(x) for x in after.findall('joint')])
            prop=after.find('link').findall('visual')[-1]
            self.assertEqual(list(map(float,prop.find('origin').get('xyz').split())),[1,-2,-3])
            self.assertEqual(list(map(float,prop.find('origin').get('rpy').split())),[.1+math.pi,-.2,-.3])
            self.assertEqual(prop.find('geometry/mesh').get('scale'),'1 1 1')
    def test_database_requires_sensor_payload_and_graph(self):
        import sqlite3
        from uw_localization.artifacts import inspect_database
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'map.db'
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE Node(id INT)');db.execute('CREATE TABLE Data(image BLOB)')
            self.assertFalse(inspect_database(path)['passed'])
            with sqlite3.connect(path) as db:
                db.execute('INSERT INTO Node VALUES(1)');db.execute('INSERT INTO Data VALUES(?)',(b'compressed_sensor_payload',))
            self.assertTrue(inspect_database(path)['passed'])
