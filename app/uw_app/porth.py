"""Explicit Porth composition and evidence helpers; no control algorithms."""
import shutil
from pathlib import Path
import yaml


def prepare(out,cfg,share):
    from uw_simulations.porth_scene import load_asset,add_cave
    from uw_robot.description import make_mesh_urdf
    directory=out.parent.parent/'assets'/cfg['cave_asset']
    asset=load_asset(directory);shutil.copy2(directory/'asset.json',out/'cave-asset.json')
    add_cave(out/'m2.scn',directory,asset)
    profile=yaml.safe_load((Path(share('uw_robot'))/'config/bluerov2_heavy.yaml').read_text())
    return make_mesh_urdf(cfg['namespace'],profile,directory)


def slam_parameters(out,cfg,share):
    p=yaml.safe_load((Path(share('uw_localization'))/'config/rtabmap_stereo.yaml').read_text())
    ns=cfg['namespace']
    p.update(use_sim_time=True,frame_id=ns+'/base_link',map_frame_id=ns+'/map',
        odom_frame_id='',database_path=str(out/'rtabmap.db'))
    p['Rtabmap/WorkingDirectory']=str(out)
    if cfg.get('survey_profile')=='known_route_capture_v1':
        # Keep visual dictionary rebuilds bounded during long acquisitions.
        # Evicted working nodes remain in the database and can be retrieved.
        p.update({'Grid/CellSize':'0.20','Grid/RangeMax':'10.0','Rtabmap/DetectionRate':'1.0','Mem/STMSize':'30',
                  'Rtabmap/MemoryThr':'600','Rtabmap/TimeThr':'250'})
    path=out/'rtabmap-parameters.yaml';path.write_text(yaml.safe_dump({'/**':{'ros__parameters':p}},sort_keys=False))
    return str(path)


def rviz_layout(layout,ns):
    manager=layout['Visualization Manager'];manager['Global Options']['Fixed Frame']=ns+'/map'
    for display in manager['Displays']:
        if display.get('Class')=='rviz_default_plugins/RobotModel':display['Name']='BlueROV2 Heavy - actual asset'
    def topic(name):return {'Value':f'/{ns}/slam/{name}','Reliability Policy':'Reliable','Durability Policy':'Volatile','Depth':1}
    manager['Displays'] += [
        {'Class':'rviz_default_plugins/PointCloud2','Name':'SLAM map - stereo measurements','Enabled':True,
         'Topic':topic('cloud_map'),'Style':'Points','Size (Pixels)':3,'Color Transformer':'RGB8','Position Transformer':'XYZ','Decay Time':0},
        {'Class':'rviz_default_plugins/Path','Name':'SLAM optimized trajectory','Enabled':True,'Color':'255; 90; 130','Topic':topic('trajectory')},
        {'Class':'rviz_default_plugins/Marker','Name':'Known Porth cutaway - NOT SLAM output','Enabled':False,'Topic':topic('known_cave')}]
    manager['Views']['Current'].update({'Target Frame':ns+'/odom','Distance':7,'Pitch':.7,'Yaw':.7,'Focal Point':{'X':1.2,'Y':0.,'Z':0.}})


# Kept as a compatibility import for existing run inspection scripts.
from uw_runtime.map_storage import inspect_database
