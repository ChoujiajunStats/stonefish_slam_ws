"""Independent post-run evaluation of original online ORB poses and saved keyframes."""
import argparse,hashlib,json,math
from pathlib import Path
import numpy as np
from uw_robot.frames import quaternion_rpy as rpy
from uw_runtime.artifacts import write_json
from uw_benchmark.cloud_viewer import write_viewer


def rows(path):
    with Path(path).open() as stream:
        for line in stream:
            yield json.loads(line)


def compare(truth,estimates):
    if not estimates:return {'status':'NOT_VERIFIED'},None
    gt=np.array([x['stamp'] for x in truth]);gp=np.array([x['position'] for x in truth]);ga=np.unwrap([rpy(x['quaternion'])[2] for x in truth])
    data=[x for x in estimates if gt[0]<=x['stamp']<=gt[-1]]
    if not data:return {'status':'NOT_VERIFIED'},None
    ts=np.array([x['stamp'] for x in data]);pos=np.array([x['position'] for x in data]);yaw=float(np.interp(ts[0],gt,ga)-rpy(data[0]['quaternion'])[2])
    c,s=math.cos(yaw),math.sin(yaw);R=np.array([[c,-s,0],[s,c,0],[0,0,1]])
    target=np.column_stack([np.interp(ts,gt,gp[:,i]) for i in range(3)])
    offset=target[0]-R@pos[0];aligned=pos@R.T+offset;error=np.linalg.norm(aligned-target,axis=1)
    return dict(status='EVALUATED',samples=len(data),rmse_m=float(np.sqrt(np.mean(error**2))),max_m=float(error.max()),final_m=float(error[-1]),
        window_sec=[float(ts[0]),float(ts[-1])],alignment='initial yaw+translation ONLY; no scale or whole-trajectory fit',initial_yaw_rad=yaw,translation=offset.tolist()),dict(time=ts,estimate=aligned,truth=target,error=error)


def evaluate(run):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    run=Path(run);output=run.parent.parent/'reports'/('orb-evaluation-'+run.name)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(exist_ok=False)
    source_paths=[run/name for name in ('orb-frames.jsonl','orb-keyframes-body.jsonl','orb-sparse-map.ply','orb-final.json','m3-samples.jsonl')]
    source={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}
    truth=[x for x in rows(run/'m3-samples.jsonl') if x['kind']=='truth']
    frames=list(rows(run/'orb-frames.jsonl'));keys=list(rows(run/'orb-keyframes-body.jsonl'))
    metrics={};series={}
    for name,sequence in [('original_online',[x for x in frames if x['valid']]),('final_optimized_keyframes',keys)]:metrics[name],series[name]=compare(truth,sequence)
    first=next((i for i,x in enumerate(frames) if x['valid']),len(frames));active=frames[first:]
    metrics.update(run_id=run.name,mode='STEREO',truth_input_to_orb=False,imu_input_to_orb=False,external_odometry_input=False,
        tracked_fraction_after_first_tracking=sum(x['valid'] for x in active)/max(1,len(active)),processed_frames=len(frames),lost_processed_frames=sum(not x['valid'] for x in active),
        latency_sec={str(p):float(np.percentile([x['latency_sec'] for x in active],p)) for p in (50,95,99,100)},
        tracking_compute_sec={str(p):float(np.percentile([x['compute_sec'] for x in active],p)) for p in (50,95,99,100)},
        final=json.loads((run/'orb-final.json').read_text()),source_sha256=source,map_product='SPARSE_LANDMARKS; dense coverage NOT_VERIFIED')
    fig,axes=plt.subplots(2,2,figsize=(13,10))
    for name,data in series.items():
        if data is None:continue
        axes[0,0].plot(data['estimate'][:,0],data['estimate'][:,1],label=name)
        axes[0,1].plot(data['time'],data['error'],label=name)
    gp=np.array([x['position'] for x in truth]);axes[0,0].plot(gp[:,0],gp[:,1],'k--',label='truth (evaluation only)');axes[0,0].axis('equal')
    axes[0,0].set(xlabel='ENU E [m]',ylabel='ENU N [m]',title='Initial-pose aligned trajectories')
    axes[0,1].set(xlabel='Acquisition sim time [s]',ylabel='Position error [m]',title='All valid overlap samples')
    t=np.array([x['stamp'] for x in frames]);axes[1,0].plot(t,[x['latency_sec'] for x in frames],label='input-to-output latency');axes[1,0].plot(t,[x['compute_sec'] for x in frames],label='TrackStereo compute');axes[1,0].set(xlabel='Sim time [s]',ylabel='Seconds')
    axes[1,1].step(t,[x['tracking_state'] for x in frames],label='native tracking state');axes[1,1].set_yticks([0,1,2,3,4],['no images','initializing','OK','recently lost','lost']);axes[1,1].set_xlabel('Sim time [s]')
    for ax in axes.flat:ax.grid(alpha=.3);ax.legend(fontsize=8)
    fig.suptitle('ORB-SLAM3 live stereo: online poses vs post-run optimized keyframes');fig.tight_layout();fig.savefig(output/'online-tracking.png',dpi=160);plt.close(fig)
    with (run/'orb-sparse-map.ply').open('rb') as f:
        while f.readline()!=b'end_header\n':pass
        xyz=np.frombuffer(f.read(),dtype='<f4').reshape(-1,3)
    colors=np.tile(np.array([70,210,255],dtype=np.uint8),(len(xyz),1));track=np.array([x['position'] for x in keys])
    if len(xyz) and len(track):
        write_viewer(output/'sparse-map.html',xyz,colors,track,0.)
        p=output/'sparse-map.html';s=p.read_text().replace('Porth 实际 SLAM 重建','ORB-SLAM3 原生稀疏地图').replace('Porth · 实际双目 SLAM 点云','Porth · ORB-SLAM3 稀疏地标').replace('全视觉表面覆盖（0.30 m）：0.0%','这是稀疏特征地图，未评价完整表面重建').replace('点云来自传感器数据库，空缺保持原样，未混入原始洞穴模型。','地图和关键帧来自本次在线 ORB Atlas 的最终状态，无洞穴资产输入。').replace('实际采集轨迹（真值辅助控制）','ORB 最终优化关键帧轨迹');p.write_text(s)
        fig=plt.figure(figsize=(12,7));ax=fig.add_subplot(projection='3d');stride=max(1,len(xyz)//50000);ax.scatter(*xyz[::stride].T,s=.5,c='#36a9ce');ax.plot(*track.T,c='crimson');ax.set(xlabel='Initial FLU x [m]',ylabel='Initial FLU y [m]',zlabel='Initial FLU z [m]',title='Final native ORB sparse map; NOT a dense surface');fig.tight_layout();fig.savefig(output/'sparse-map.png',dpi=160);plt.close(fig)
    write_json(output/'metrics.json',metrics)
    assert source=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}
    print(json.dumps(dict(report=str(output),**metrics),indent=2));return output


def main():
    p=argparse.ArgumentParser();p.add_argument('run_dir');a=p.parse_args();evaluate(a.run_dir)
if __name__=='__main__':main()
