"""Reopen a completed SLAM database with RTAB-Map and export a new report.

The original run is read-only. A separate copy absorbs any backend side effects.
"""
import argparse,hashlib,json,shutil,subprocess,uuid
from pathlib import Path
from datetime import datetime,timezone
from uw_localization.artifacts import inspect_database


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def trajectory_error(source,poses,report,alignment=None):
    """Evaluation only: map-aligned estimates versus simulator truth timestamps."""
    import math,numpy as np
    metrics=alignment if alignment is not None else json.loads((source/'m3-metrics.json').read_text())['metrics']
    angle=metrics['alignment_yaw_rad'];c,s=math.cos(angle),math.sin(angle)
    rotation=np.array([[c,-s,0],[s,c,0],[0,0,1]]);translation=np.array(metrics['alignment_translation'])
    truth=[]
    with (source/'m3-samples.jsonl').open() as stream:
        for line in stream:
            row=json.loads(line)
            if row.get('kind')=='truth':truth.append([row['stamp'],*row['position']])
    true=np.array(truth);estimated=np.loadtxt(poses,comments='#',ndmin=2)
    valid=(estimated[:,0]>=true[0,0])&(estimated[:,0]<=true[-1,0]);estimated=estimated[valid]
    if not len(estimated):return {'status':'NOT_VERIFIED','reason':'No timestamp overlap'}
    target=np.column_stack([np.interp(estimated[:,0],true[:,0],true[:,i]) for i in (1,2,3)])
    aligned=estimated[:,1:4]@rotation.T+translation;errors=np.linalg.norm(aligned-target,axis=1)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    axes[0].plot(target[:,0],target[:,1],label='Truth (evaluation only)');axes[0].plot(aligned[:,0],aligned[:,1],label='RTAB-Map optimized')
    axes[0].axis('equal');axes[0].legend();axes[0].set(xlabel='ENU X (m)',ylabel='ENU Y (m)')
    axes[1].plot(estimated[:,0],errors);axes[1].set(xlabel='Simulation time (s)',ylabel='Position error (m)')
    fig.tight_layout();fig.savefig(report/'reloaded-trajectory.png',dpi=160);plt.close(fig)
    return dict(status='MEASURED',samples=len(errors),position_rmse_m=float(np.sqrt(np.mean(errors**2))),
        position_max_m=float(errors.max()),alignment=metrics.get('alignment_description','Initial VIO yaw/translation alignment from m3-metrics; no trajectory best-fit'),
        truth_input_to_slam=False)


def export(data,run_id):
    if Path(run_id).name!=run_id or run_id in ('.','..'):raise ValueError('Expected one run directory name')
    data=Path(data);source=data/'runs'/run_id;manifest=json.loads((source/'manifest.json').read_text())
    if manifest.get('milestone') not in ('PORTH_SLAM_DEMO','PORTH_SURVEY') or manifest.get('status')=='RUNNING':raise ValueError('Expected a completed Porth SLAM run')
    report=data/'reports'/('slam-export-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]);report.mkdir(parents=True)
    original=source/'rtabmap.db';before=sha(original);copy=report/'rtabmap.db';shutil.copy2(original,copy)
    # Saved optimized poses cover only the last working graph when memory
    # management is active. Re-optimize all retained nodes for a whole map.
    import yaml
    parameters=yaml.safe_load((source/'rtabmap-parameters.yaml').read_text())['/**']['ros__parameters']
    bounded_memory=float(parameters.get('Rtabmap/MemoryThr',0))>0 or float(parameters.get('Rtabmap/TimeThr',0))>0
    optimization='0' if bounded_memory else '2'
    commands=[['rtabmap-info',str(copy)],['rtabmap-export','--cloud','--poses','--opt',optimization,'--decimation','4','--voxel','0.06','--max_range','8','--output','reloaded','--output_dir',str(report),str(copy)]]
    exits=[]
    for i,cmd in enumerate(commands):
        with (report/f'command-{i}.log').open('w') as log:
            result=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,timeout=1200 if manifest.get('milestone')=='PORTH_SURVEY' else 180)
        exits.append(result.returncode)
        if result.returncode:break
    clouds=list(report.glob('reloaded*.ply'));poses=list(report.glob('reloaded*.txt'))
    points=0
    if clouds:
        with clouds[0].open('rb') as stream:
            for _ in range(60):
                line=stream.readline().decode('ascii',errors='replace').strip()
                if line.startswith('element vertex '):points=int(line.split()[-1])
                if line=='end_header':break
    pose_count=sum(1 for path in poses for line in path.read_text().splitlines() if line and not line.startswith('#'))
    result=dict(source_run=run_id,source_database_sha256=before,source_unchanged=sha(original)==before,
        image_id=manifest['image_id'],commands=commands,exit_codes=exits,reopened=inspect_database(copy),
        exported_points=points,exported_pose_rows=pose_count,
        scope='RTAB-Map database reopen and saved optimized map export; not a new sensor relocalization trial',
        files={p.name:sha(p) for p in report.iterdir() if p.is_file()})
    result['exporter_sha256']=sha(__file__)
    result['full_global_reoptimization']=bounded_memory
    if bounded_memory:result['scope']='Full global optimization of retained graph after bounded online working memory; not a new sensor relocalization trial'
    if poses and (source/'m3-metrics.json').exists():result['trajectory_evaluation']=trajectory_error(source,poses[0],report)
    result['files']={p.name:sha(p) for p in report.iterdir() if p.is_file()}
    result['status']='PASS' if exits==[0,0] and result['source_unchanged'] and points>1000 and pose_count>0 else 'FAIL'
    (report/'reload-metrics.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(report=str(report),**result),indent=2))
    return 0 if result['status']=='PASS' else 1


def main():
    parser=argparse.ArgumentParser();parser.add_argument('run_id');parser.add_argument('--data-root',default='/data');a=parser.parse_args()
    raise SystemExit(export(a.data_root,a.run_id))


if __name__=='__main__':main()
