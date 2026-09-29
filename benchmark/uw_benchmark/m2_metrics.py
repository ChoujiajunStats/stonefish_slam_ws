"""Offline M2 metrics: single initial yaw/translation gauge alignment, never scale fit."""
import math
import numpy as np
from uw_controller.core import rpy


def rotation(q):
    x,y,z,w=q
    return np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
                     [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
                     [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])


def evaluate(truth,estimates):
    if len(estimates)<20 or len(truth)<20:return {},None
    gt=np.array([r['stamp'] for r in truth])
    # A deliberate clock rewind has no single interpolation epoch. Do not report
    # trajectory accuracy across that fault as if timestamps remained ordered.
    if np.any(np.diff(gt)<=0):return {},None
    est=[r for r in estimates if gt[0]<=r['stamp']<=gt[-1]]
    if len(est)<20:return {},None
    times=np.array([r['stamp'] for r in est]);p=np.array([r['position'] for r in est]);v=np.array([r['velocity'][:3] for r in est]);angles=np.array([rpy(r['quaternion']) for r in est])
    gp0=np.array([r['position'] for r in truth]);gv0=np.array([r['velocity'][:3] for r in truth]);ga0=np.unwrap(np.array([rpy(r['quaternion']) for r in truth]),axis=0)
    gp=np.stack([np.interp(times,gt,gp0[:,i]) for i in range(3)],axis=1)
    gv=np.stack([np.interp(times,gt,gv0[:,i]) for i in range(3)],axis=1)
    ga=np.stack([np.interp(times,gt,ga0[:,i]) for i in range(3)],axis=1)
    yaw=ga[0,2]-angles[0,2];c,s=math.cos(yaw),math.sin(yaw);R=np.array([[c,-s,0],[s,c,0],[0,0,1]])
    aligned=(p-p[0])@R.T+gp[0]
    angular=angles-ga;angular[:,2]+=yaw;angular=np.arctan2(np.sin(angular),np.cos(angular))
    err=aligned-gp;verr=v-gv
    metrics=dict(samples=len(est),alignment_yaw_rad=float(yaw),alignment_translation=(gp[0]-R@p[0]).tolist(),
        position_rmse_m=float(np.sqrt(np.mean(np.sum(err**2,axis=1)))),position_max_m=float(np.linalg.norm(err,axis=1).max()),
        velocity_rmse_m_s=np.sqrt(np.mean(verr**2,axis=0)).tolist(),attitude_rmse_deg=np.degrees(np.sqrt(np.mean(angular**2,axis=0))).tolist(),
        final_position_error_m=float(np.linalg.norm(err[-1])),truth_travel_m=float(np.linalg.norm(np.diff(gp,axis=0),axis=1).sum()),
        full_window_sec=[float(times[0]),float(times[-1])])
    return metrics,dict(times=times,truth=gp,estimate=aligned,truth_velocity=gv,estimate_velocity=v,angles=angles,truth_angles=ga,yaw_offset=yaw)


def render(folder,truth,estimates,statuses):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    _,data=evaluate(truth,estimates)
    if data:
        t=data['times']-data['times'][0]
        fig,axes=plt.subplots(3,2,figsize=(12,9),sharex=True)
        for i in range(3):
            axes[i,0].plot(t,data['truth_velocity'][:,i],label='Truth (evaluation only)');axes[i,0].plot(t,data['estimate_velocity'][:,i],label='OpenVINS')
            axes[i,0].set_ylabel(('vx','vy','vz')[i]+' [m/s]')
            angles=data['angles'][:,i]+(data['yaw_offset'] if i==2 else 0)
            axes[i,1].plot(t,np.degrees(data['truth_angles'][:,i]),label='Truth');axes[i,1].plot(t,np.degrees(angles),label='OpenVINS');axes[i,1].set_ylabel(('roll','pitch','yaw')[i]+' [deg]')
        for ax in axes.flat:ax.grid(alpha=.3);ax.legend(fontsize=7)
        fig.suptitle('Actual sensor-only estimate; initial yaw gauge aligned for evaluation');fig.tight_layout();fig.savefig(folder/'figures/velocity-attitude.png',dpi=140);plt.close(fig)
        fig=plt.figure(figsize=(9,7));ax=fig.add_subplot(projection='3d')
        for key,label in [('truth','Truth'),('estimate','OpenVINS (initial yaw + translation aligned)')]:ax.plot(*data[key].T,label=label)
        ax.set(xlabel='ENU E [m]',ylabel='ENU N [m]',zlabel='ENU U [m]');ax.legend();fig.tight_layout();fig.savefig(folder/'figures/trajectory.png',dpi=140);plt.close(fig)
    if statuses:
        fig,axes=plt.subplots(2,1,figsize=(10,6),sharex=True)
        t=np.array([x['elapsed'] for x in statuses]);codes={'INITIALIZING':0,'TRACKING':1,'DEGRADED':2,'FAULT':3}
        axes[0].step(t,[codes[x['state']] for x in statuses]);axes[0].set_yticks(list(codes.values()),list(codes));axes[0].grid(alpha=.3)
        axes[1].plot(t,[x['features'] for x in statuses],label='Detected corners');axes[1].plot(t,[x['msckf_used_features'] for x in statuses],label='Features used by MSCKF');axes[1].legend();axes[1].set_xlabel('Wall time from case start [s]')
        fig.tight_layout();fig.savefig(folder/'figures/health-features.png',dpi=140);plt.close(fig)


def render_fault(folder,terminal,statuses,estimates,injection_wall):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(4,1,figsize=(11,10),sharex=True)
    times=np.array([int(r['wall_ns'])*1e-9-injection_wall for r in terminal])
    for axis,key,unit in zip(axes[:3],('receiver_setpoint','rpm','thrust_N'),('Native setpoint','Measured RPM','Measured thrust [N]')):
        values=np.array([[float(v) for v in r[key]] for r in terminal])
        for i in range(8):axis.plot(times,values[:,i],label=terminal[0]['names'][i])
        axis.set_ylabel(unit);axis.grid(alpha=.3)
    axes[0].legend(fontsize=7,ncol=4)
    codes={'INITIALIZING':0,'TRACKING':1,'DEGRADED':2,'FAULT':3}
    axes[3].step([s['wall']-injection_wall for s in statuses],[codes[s['state']] for s in statuses],label='Estimator health')
    axes[3].plot([s['wall']-injection_wall for s in estimates],[-.3]*len(estimates),'|',label='Actual estimate received')
    axes[3].set_yticks(list(codes.values()),list(codes));axes[3].legend(fontsize=8)
    for ax in axes:ax.axvline(0,color='r',linestyle='--');ax.set_xlim(-2,6)
    axes[3].set_xlabel('Monotonic wall time from injection / explicit diagnostic DISARM [s]')
    fig.suptitle('Sensor fault diagnosis: test runner explicitly DISARMs truth-controlled motion')
    fig.tight_layout();fig.savefig(folder/'figures/fault-timeline.png',dpi=140);plt.close(fig)
