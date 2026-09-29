"""Native ORB stereo settings from an explicit robot calibration and defaults file."""
import hashlib,json,shutil,math
from pathlib import Path
import yaml
from uw_perception.contracts import intrinsics


def prepare(out, namespace, profile, defaults):
    out, defaults = Path(out), Path(defaults)
    params=yaml.safe_load(defaults.read_text())
    left,right=[profile['cameras'][side] for side in ('left','right')]
    for key in ('width','height','horizontal_fov_deg','rpy_frd'):
        if left[key]!=right[key]:raise ValueError('ORB requires already rectified identical cameras')
    if left['xyz_frd'][::2]!=right['xyz_frd'][::2]:raise ValueError('Non-horizontal stereo geometry')
    if any(abs(a-b)>1e-8 for a,b in zip(left['rpy_frd'],[math.pi/2,0.,math.pi/2])):raise ValueError('Unexpected native optical axes')
    baseline=right['xyz_frd'][1]-left['xyz_frd'][1]
    if baseline<=0 or abs(baseline-profile['stereo_baseline_m'])>1e-9:raise ValueError('Invalid stereo baseline')
    fx,fy,cx,cy=intrinsics(left['width'],left['height'],left['horizontal_fov_deg'])
    x,y,z=left['xyz_frd']
    # Optical right/down/forward -> body FLU, including lever arm.
    matrix=[0.,0.,1.,x,-1.,0.,0.,-y,0.,-1.,0.,-z,0.,0.,0.,1.]
    values={'Camera.type':'PinHole','Camera.fx':fx,'Camera.fy':fy,'Camera.cx':cx,'Camera.cy':cy,
        'Camera.k1':0.0,'Camera.k2':0.0,'Camera.p1':0.0,'Camera.p2':0.0,'Camera.k3':0.0,
        'Camera.width':left['width'],'Camera.height':left['height'],'Camera.fps':20.0,'Camera.RGB':1,
        'Camera.bf':fx*baseline,'ThDepth':params['close_depth_baselines'],
        'ORBextractor.nFeatures':params['features'],'ORBextractor.scaleFactor':params['scale_factor'],
        'ORBextractor.nLevels':params['pyramid_levels'],'ORBextractor.iniThFAST':params['initial_fast_threshold'],
        'ORBextractor.minThFAST':params['minimum_fast_threshold'],
        'Viewer.KeyFrameSize':.05,'Viewer.KeyFrameLineWidth':1.,'Viewer.GraphLineWidth':.9,'Viewer.PointSize':2.,
        'Viewer.CameraSize':.08,'Viewer.CameraLineWidth':3.,'Viewer.ViewpointX':0.,'Viewer.ViewpointY':-.7,
        'Viewer.ViewpointZ':-1.8,'Viewer.ViewpointF':500.,'System.SaveAtlasToFile':'orb-atlas'}
    settings=out/'orbslam3-settings.yaml'
    settings.write_text('%YAML:1.0\n'+''.join(k+': '+(json.dumps(v) if isinstance(v,str) else str(v))+'\n' for k,v in values.items())+
        'Research.T_body_camera: !!opencv-matrix\n  rows: 4\n  cols: 4\n  dt: f\n  data: '+str(matrix)+'\n')
    shutil.copy2(defaults,out/'orbslam3-parameters.yaml')
    (out/'orb-contract.json').write_text(json.dumps(dict(mode='STEREO',input='live_exact_stereo_only',truth_input=False,
        external_odometry_input=False,imu_input=False,baseline_m=baseline,T_body_camera=matrix,intrinsics=[fx,fy,cx,cy],
        map_frame=namespace+'/map',map_gauge='first tracked camera transformed into initial body FLU',
        rviz_robot_pose='ORB map->orb_body only; no transform connecting independent OpenVINS odom',
        preprocessing=dict(grayscale='RGB2GRAY',clahe_clip_limit=params['clahe_clip_limit'],clahe_grid_size=params['clahe_grid_size']),map_product='sparse landmarks; not a dense surface',settings_sha256=hashlib.sha256(settings.read_bytes()).hexdigest()),indent=2)+'\n')
    return {'frame_prefix':namespace,'run_dir':str(out),'settings_path':str(settings),'maximum_input_age_sec':float(params['maximum_input_age_sec']),'maximum_pending_per_side':params['maximum_pending_per_side'],'map_publish_hz':float(params['map_publish_hz']),'clahe_clip_limit':float(params['clahe_clip_limit']),'clahe_grid_size':params['clahe_grid_size']}

