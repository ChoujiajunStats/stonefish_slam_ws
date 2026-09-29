"""Plots of measured runs, predictions explicitly separated from native feedback."""
import numpy as np
from uw_benchmark.m2_metrics import evaluate


def render(out,truth,estimates,navigation,terminal,health,injection):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    _,d=evaluate(truth,estimates)
    if d:
        fig,axes=plt.subplots(3,2,figsize=(12,9),sharex=True)
        t=d['times'];nav=[x for x in navigation if 'target_velocity' in x]
        nt=np.array([x['received_wall'] for x in nav]);et=np.array([x['wall'] for x in estimates]);st=np.array([x['stamp'] for x in estimates])
        angles=np.unwrap(d['angles'],axis=0);angles[:,2]+=d['yaw_offset']
        for i in range(3):
            axes[i,0].plot(t,d['truth_velocity'][:,i],label='Truth evaluation');axes[i,0].plot(t,d['estimate_velocity'][:,i],label='OpenVINS feedback')
            if nav:axes[i,0].plot(np.interp(nt,et,st),[x['target_velocity'][i] for x in nav],label='Target',alpha=.7)
            axes[i,0].set_ylabel(('vx','vy','vz')[i]+' m/s')
            axes[i,1].plot(t,np.degrees(d['truth_angles'][:,i]),label='Truth');axes[i,1].plot(t,np.degrees(angles[:,i]),label='OpenVINS');axes[i,1].set_ylabel(('roll','pitch','yaw')[i]+' deg')
        for a in axes.flat:a.grid(alpha=.3);a.legend(fontsize=7)
        fig.tight_layout();fig.savefig(out/'figures/velocity-attitude.png',dpi=130);plt.close(fig)
        fig=plt.figure(figsize=(9,7));ax=fig.add_subplot(projection='3d')
        for key,label in [('truth','Truth evaluation'),('estimate','Estimated feedback (initial gauge aligned)')]:ax.plot(*d[key].T,label=label)
        ax.set(xlabel='ENU E m',ylabel='ENU N m',zlabel='ENU U m');ax.legend();fig.tight_layout();fig.savefig(out/'figures/trajectory.png',dpi=130);plt.close(fig)
    if terminal:
        origin=injection or int(terminal[0]['wall_ns'])*1e-9;t=np.array([int(x['wall_ns'])*1e-9-origin for x in terminal])
        fig,axes=plt.subplots(3,1,figsize=(11,8),sharex=True)
        for a,key,unit in zip(axes,('receiver_setpoint','rpm','thrust_N'),('Receiver setpoint','Actual RPM','Actual thrust N')):
            values=np.array([[float(v) for v in x[key]] for x in terminal]);a.plot(t,values);a.set_ylabel(unit);a.grid(alpha=.3)
            if injection:a.axvline(0,color='r',linestyle='--');a.set_xlim(-2,6)
        axes[-1].set_xlabel('Monotonic seconds from '+('fault injection' if injection else 'first feedback'))
        fig.tight_layout();fig.savefig(out/('figures/fault-timeline.png' if injection else 'figures/actuators.png'),dpi=130);plt.close(fig)
