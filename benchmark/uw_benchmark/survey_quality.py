"""Post-run map precision and untrimmed centerline audit; never used online."""
import argparse,csv,hashlib,json,math
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from uw_simulations.porth_assets import read_obj
from uw_simulations.surface import SurfaceQuery
from uw_simulations.survey_plan import world


def evaluate(data,run_id,export_dir):
    root=Path(data)
    if Path(run_id).name!=run_id or Path(export_dir).name!=export_dir:raise ValueError('Expected run and report names')
    run=root/'runs'/run_id;report=root/'reports'/export_dir
    if (report/'quality.json').exists():raise ValueError('Refuse to overwrite completed analysis')
    if json.loads((run/'manifest.json').read_text())['status']=='RUNNING':raise ValueError('Run must be closed')
    plan=json.loads((run/'survey-plan.json').read_text());asset=root/'assets/porth_sump9_v1'
    xyz=np.load(report/'registered-slam-cloud.npz')['xyz_enu'];rng=np.random.default_rng(20260924)
    points=xyz[rng.choice(len(xyz),min(100000,len(xyz)),replace=False)]
    # Undo only the known asset placement, not the reconstruction drift.
    a=plan['cave_yaw_ned'];c,s=math.cos(a),math.sin(a);rot=np.array([[c,-s,0],[s,c,0],[0,0,1]])
    ned=points[:,[1,0,2]]*np.array([1,1,-1]);local=(ned-plan['cave_offset_ned'])@rot/plan['scale']
    v,f=read_obj(asset/'visual.obj');query=SurfaceQuery(v[f]);distance=np.abs(query.signed(local))*plan['scale']
    actual=[]
    with (run/'m3-samples.jsonl').open() as stream:
        for line in stream:
            p=json.loads(line)
            if p['kind']=='truth':actual.append(p['position'])
    source=list(csv.DictReader((asset/'navigation_centerline.csv').open()))
    center=np.array([[float(p[k]) for k in ('north_m','east_m','down_m')] for p in source])*plan['scale']
    center=world(center,plan);center_distance=cKDTree(actual).query(center,workers=2)[0]
    result=dict(run_id=run_id,scope='POST_RUN_ONLY_NOT_SLAM_INPUT',analysis_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        cloud_sample_count=len(points),sampling_seed=20260924,
        cloud_precision_fraction={str(t):float(np.mean(distance<=t)) for t in (.15,.3,.5)},
        cloud_surface_distance_quantiles_m=np.percentile(distance,[5,25,50,75,95]).tolist(),
        nearest_surface_method='Exact point-to-triangle distance among 24 nearest triangle centroids; approximate global nearest surface',
        untrimmed_main_centerline_points=len(center),planned_main_points=len(plan['main_enu']),
        full_centerline_fraction_within_trajectory_distance={str(t):float(np.mean(center_distance<=t)) for t in (1.,3.,5.)},
        full_centerline_maximum_distance_to_trajectory_m=float(center_distance.max()),
        limitations='Trajectory proximity is not visibility or reconstructed surface coverage. Open-mesh side signs ignored for unsigned distance. No alignment fitting or truth correction applied.')
    (report/'quality.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


def main():
    p=argparse.ArgumentParser();p.add_argument('run_id');p.add_argument('export_dir');p.add_argument('--data-root',default='/data');a=p.parse_args();evaluate(a.data_root,a.run_id,a.export_dir)


if __name__=='__main__':main()
