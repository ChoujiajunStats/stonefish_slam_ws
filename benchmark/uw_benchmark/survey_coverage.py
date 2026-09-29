"""Offline area-weighted comparison, never an input or correction to SLAM."""
import argparse,hashlib,json,math
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from uw_simulations.porth_assets import read_obj
from uw_simulations.survey_plan import world


def read_cloud(path):
    fields=[];count=0;element=None;types={'float':'<f4','double':'<f8','uchar':'u1','uint':'<u4','int':'<i4'}
    with Path(path).open('rb') as stream:
        while True:
            line=stream.readline().decode('ascii').strip()
            if not line:raise ValueError('Unexpected PLY EOF')
            parts=line.split()
            if parts[:2]==['format','ascii']:raise ValueError('Expected binary cloud')
            if parts[0]=='element':element=parts[1];count=int(parts[2]) if element=='vertex' else count
            if parts[0]=='property' and element=='vertex':fields.append((parts[2],types[parts[1]]))
            if line=='end_header':break
        rows=np.fromfile(stream,dtype=np.dtype(fields),count=count)
    xyz=np.column_stack([rows[x] for x in ('x','y','z')]);rgb=np.column_stack([rows[x] for x in ('red','green','blue')])
    valid=np.isfinite(xyz).all(axis=1);return xyz[valid],rgb[valid]


def evaluate(data,run_id,export_dir):
    data=Path(data)
    if Path(run_id).name!=run_id:raise ValueError('Expected run directory name')
    source=data/'runs'/run_id;report=Path(export_dir)
    if not report.is_absolute():report=data/'reports'/report
    if not report.resolve().is_relative_to((data/'reports').resolve()):raise ValueError('Expected report in project data root')
    if (report/'coverage.json').exists():raise ValueError('Coverage report already exists')
    plan=json.loads((source/'survey-plan.json').read_text());metrics=json.loads((source/'m3-metrics.json').read_text())
    asset_dir=data/'assets'/'porth_sump9_v1';asset=json.loads((asset_dir/'asset.json').read_text())
    for k in ('scale','cave_offset_ned','cave_yaw_ned'):asset[k]=plan[k]
    xyz,rgb=read_cloud(next(report.glob('reloaded*.ply')))
    alignment=metrics['metrics'];alignment_description='Initial VIO yaw and translation only; no best-fit or nonrigid correction'
    export_record=json.loads((report/'reload-metrics.json').read_text())
    if export_record.get('recomputed_stereo_odometry'):
        if export_record['source_run']!=run_id or not export_record['source_unchanged']:raise ValueError('Offline source provenance mismatch')
        alignment=export_record['evaluation_alignment'];alignment_description=alignment['alignment_description']
    angle=alignment['alignment_yaw_rad'];c,s=math.cos(angle),math.sin(angle)
    rotation=np.array([[c,-s,0],[s,c,0],[0,0,1]])
    xyz=xyz@rotation.T+alignment['alignment_translation']
    print('Reading full visual mesh and sampling its surface...',flush=True)
    vertices,faces=read_obj(asset_dir/'visual.obj');tri=vertices[faces]*plan['scale']
    area=np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1)/2
    seed=20260924;rng=np.random.default_rng(seed);n=300000
    chosen=rng.choice(len(tri),n,p=area/area.sum());u=np.sqrt(rng.random(n));v=rng.random(n)
    samples=(1-u[:,None])*tri[chosen,0]+(u*(1-v))[:,None]*tri[chosen,1]+(u*v)[:,None]*tri[chosen,2]
    samples=world(samples,asset);tree=cKDTree(xyz);dist=tree.query(samples,workers=4)[0]
    full_bounds=np.array([world(vertices*plan['scale'],asset).min(axis=0),world(vertices*plan['scale'],asset).max(axis=0)])
    # Coverage uses no best-fit deformation, ICP or scaling. Reconstruction
    # errors remain visible as gaps against the originally registered mesh.
    coverage={str(t):float(np.mean(dist<=t)) for t in (.15,.30,.50)}
    ci={str(t):float(1.96*math.sqrt(coverage[str(t)]*(1-coverage[str(t)])/n)) for t in (.15,.30,.50)}
    rows=[]
    with (source/'m3-samples.jsonl').open() as stream:
        for line in stream:
            p=json.loads(line)
            if p['kind']=='truth':rows.append(p['position'])
    actual=np.array(rows);route=np.array(plan['route_enu']);route_dist=cKDTree(actual).query(route,workers=4)[0]
    corridors={}
    for name,p in [('main',plan['main_enu'])]+[(f'branch_{i+1}',p) for i,p in enumerate(plan['branches_enu'])]:
        p=np.array(p);d=cKDTree(actual).query(p,workers=4)[0]
        corridors[name]=dict(centerline_points=len(p),fraction_within_1m_of_actual_trajectory=float(np.mean(d<1)),maximum_distance_to_actual_m=float(d.max()))
    result=dict(source_run=run_id,source_plan_sha256=hashlib.sha256((source/'survey-plan.json').read_bytes()).hexdigest(),
        control_state_source='PRIVILEGED_DEBUG',slam_truth_input=False,known_asset_used_only_for_planning_and_evaluation=True,
        coordinate_alignment=alignment_description,recomputed_stereo_odometry=bool(export_record.get('recomputed_stereo_odometry')),
        analysis_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        full_visual_triangles=len(faces),full_visual_surface_area_m2=float(area.sum()),
        surface_sample_count=n,uniform_area_sampling_seed=seed,surface_coverage_fraction=coverage,monte_carlo_95pct_halfwidth=ci,
        surface_distance_quantiles_m=np.percentile(dist,[5,25,50,75,95]).tolist(),
        cloud_points=len(xyz),known_mesh_bounds_enu_m=full_bounds.tolist(),cloud_bounds_enu_m=[xyz.min(axis=0).tolist(),xyz.max(axis=0).tolist()],
        route_spatial_coverage_within_1m=float(np.mean(route_dist<1)),corridors=corridors,
        limitation='Surface proximity includes stereo noise and pose drift; does not establish watertightness, texture quality, or full visibility. Imported mesh is not merged into output.')
    (report/'coverage.json').write_text(json.dumps(result,indent=2)+'\n')
    np.savez_compressed(report/'surface-coverage-samples.npz',points_enu=samples,distance_m=dist)
    np.savez_compressed(report/'registered-slam-cloud.npz',xyz_enu=xyz,rgb=rgb)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,1,figsize=(16,12));shown=np.arange(0,n,3)
    axes[0].scatter(samples[shown,0],samples[shown,1],c=np.where(dist[shown]<.3,'#087f5b','#d4d4d4'),s=.3)
    axes[0].plot(actual[:,0],actual[:,1],color='#d9480f',lw=.6,label='Actual thruster-driven trajectory')
    axes[0].set_title(f'Full known visual surface: {coverage["0.3"]:.1%} within 0.30 m of measured SLAM cloud')
    step=max(1,len(xyz)//100000);axes[1].scatter(xyz[::step,0],xyz[::step,1],c=rgb[::step]/255.,s=.25)
    axes[1].set_title('Reconstructed stereo cloud only; imported cave excluded')
    for ax in axes:ax.axis('equal');ax.set(xlabel='ENU E (m)',ylabel='ENU N (m)');ax.grid(alpha=.2)
    axes[0].legend();fig.tight_layout();fig.savefig(report/'whole-cave-coverage.png',dpi=160);plt.close(fig)
    fig=plt.figure(figsize=(15,9));ax=fig.add_subplot(projection='3d');step=max(1,len(xyz)//120000)
    ax.scatter(*xyz[::step].T,c=rgb[::step]/255.,s=.25);ax.plot(*actual.T,lw=.5,color='red');ax.set(xlabel='E (m)',ylabel='N (m)',zlabel='U (m)',title='Actual stereo reconstruction and trajectory')
    ax.set_box_aspect(np.maximum(xyz.max(axis=0)-xyz.min(axis=0),1));fig.tight_layout();fig.savefig(report/'reconstruction-3d.png',dpi=180);plt.close(fig)
    from uw_benchmark.cloud_viewer import write_viewer
    write_viewer(report/'reconstruction.html',xyz,rgb,actual,coverage['0.3'])
    print(json.dumps(result,indent=2))


def main():
    p=argparse.ArgumentParser();p.add_argument('run_id');p.add_argument('export_dir');p.add_argument('--data-root',default='/data');a=p.parse_args();evaluate(a.data_root,a.run_id,a.export_dir)


if __name__=='__main__':main()
