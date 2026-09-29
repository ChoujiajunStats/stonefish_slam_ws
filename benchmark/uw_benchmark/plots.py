"""Standalone figures made only from this run's recorded execution samples."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def render(folder):
    folder=Path(folder);rows=[json.loads(s) for s in (folder/'control-samples.jsonl').read_text().splitlines()]
    state=[r for r in rows if r['kind']=='state'];terminal=[r for r in rows if r['kind']=='terminal']
    if not state or not terminal:return
    start=state[0]['wall'];t=np.array([r['wall']-start for r in state]);vel=np.array([r['velocity'] for r in state]);target=np.array([r['target'] for r in state])
    angles=np.degrees(np.array([r['rpy'] for r in state]));position=np.array([r['position'] for r in state])
    output=folder/'figures';output.mkdir(exist_ok=True)
    plt.rcParams.update({'font.size':9,'axes.grid':True,'grid.alpha':.25})
    fig,axes=plt.subplots(3,2,figsize=(12,9),sharex=True)
    for i,(name,j) in enumerate([('vx [m/s]',0),('vy [m/s]',1),('vz [m/s]',2),('yaw rate [rad/s]',5)]):
        ax=axes.flat[i];ax.plot(t,vel[:,j],label='Measured (simulation truth)');ax.plot(t,target[:,i],'--',label='Target');ax.set_ylabel(name);ax.legend(fontsize=7)
    axes[2,0].plot(t,angles[:,0],label='roll');axes[2,0].plot(t,angles[:,1],label='pitch');axes[2,0].set_ylabel('Level attitude [deg]');axes[2,0].legend()
    axes[2,1].plot(t,angles[:,2],label='yaw');axes[2,1].set_ylabel('Yaw [deg]');axes[2,1].legend()
    for ax in axes[2]:ax.set_xlabel('Wall time from first state [s]')
    fig.suptitle(folder.name+'\nPRIVILEGED_DEBUG / simulation research',fontsize=10);fig.tight_layout();fig.savefig(output/'velocity-attitude.png',dpi=150);plt.close(fig)
    ft=np.array([r['wall_ns']*1e-9-start for r in terminal]);names=terminal[0]['names']
    fig,axes=plt.subplots(3,1,figsize=(12,8),sharex=True)
    for ax,key,label in zip(axes,['applied_setpoint','rpm','thrust_N'],['Actual applied setpoint','Native RPM','Native thrust [N]']):
        values=np.array([r[key] for r in terminal]);ax.plot(ft,values);ax.set_ylabel(label)
    axes[0].legend(names,ncol=4,fontsize=7);axes[-1].set_xlabel('Wall time [s]');fig.tight_layout();fig.savefig(output/'native-actuators.png',dpi=150);plt.close(fig)
    fig=plt.figure(figsize=(8,6));ax=fig.add_subplot(projection='3d');ax.plot(position[:,0],position[:,1],position[:,2]);ax.scatter(*position[0],label='start');ax.scatter(*position[-1],label='end');ax.set(xlabel='ENU East [m]',ylabel='ENU North [m]',zlabel='ENU Up [m]');ax.legend();fig.tight_layout();fig.savefig(output/'trajectory.png',dpi=150);plt.close(fig)
    events=[json.loads(s) for s in (folder/'control-events.jsonl').read_text().splitlines()]
    injection=next((e for e in events if e['event']=='injection'),None)
    if injection:
        it=injection['wall_ns']*1e-9
        fig,axes=plt.subplots(3,1,figsize=(10,7),sharex=True)
        for ax,key,label in zip(axes,['applied_setpoint','rpm','thrust_N'],['max |applied setpoint|','max |native RPM|','max |native thrust| [N]']):
            ax.plot(ft+start-it,np.max(np.abs([r[key] for r in terminal]),axis=1));ax.axvline(0,color='red',ls='--',label='injection');ax.axvline(.5,color='orange',ls=':',label='neutralization deadline');ax.set_ylabel(label);ax.set_xlim(-1,2.5)
        axes[0].legend();axes[-1].set_xlabel('Wall time from injection [s]');fig.tight_layout();fig.savefig(output/'fault-timeline.png',dpi=150);plt.close(fig)
