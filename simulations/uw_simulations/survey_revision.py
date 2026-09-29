"""Deterministic revision after observed visual degeneration at the main end."""
import hashlib,json,math
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from uw_simulations.survey_plan import resample,world

def revise(root):
    root=Path(root);old=json.loads((root/'porth-survey-v4/plan.json').read_text());p=np.array(old['route_enu'])
    # Remove the final 4.6 m of the main passage excursion, retaining the screened
    # path in both directions. No shortcut through rock is introduced.
    turn=1204;arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
    # Detect first actual reversal from repeated route point (main end).
    for i in range(1100,1300):
     if np.linalg.norm(p[i-1]-p[i+1])<1e-6:turn=i;break
    lo=int(np.argmin(abs(arc-(arc[turn]-4.6))));hi=turn+int(np.argmin(np.linalg.norm(p[turn:]-p[lo],axis=1)))
    p=np.vstack([p[:lo+1],p[hi+1:]])
    # Canonical outward view of each passage, retained when moving backwards.
    reference=[];headings=[]
    for line in [old['main_enu'],*old['branches_enu']]:
     line=resample(np.array(line),.15)
     for i,point in enumerate(line):
      a=max(0,i-3);b=min(len(line)-1,i+3);delta=line[b]-line[a]
      if np.linalg.norm(delta[:2])<.01:
       a=max(0,i-12);b=min(len(line)-1,i+12);delta=line[b]-line[a]
      reference.append(point);headings.append(math.atan2(delta[1],delta[0]))
    ids=cKDTree(reference).query(p)[1];yaw=np.array(headings)[ids]
    # Lamps above the centerline, outside the near-camera forward view. They have
    # no physical collision shape and do not change the vehicle.
    lamps=np.array(old['lights_enu']);lamps[:,2]+=.5
    new=dict(old,version='porth-survey-v5',route_enu=p.tolist(),route_yaw_enu=yaw.tolist(),
     route_length_m=float(np.linalg.norm(np.diff(p,axis=0),axis=1).sum()),lights_enu=lamps.tolist(),
     heading_policy='Canonical outward passage view retained during reverse travel',spawn_yaw_enu_deg=90.,
     revision='Trim unsafe visual end approach by 4.6 m; reverse travel with retained view; raise lights 0.5 m',
     previous_plan_sha256=hashlib.sha256((root/'porth-survey-v4/plan.json').read_bytes()).hexdigest())
    # Store scaled native geometry consistently for review.
    angle=new['cave_yaw_ned'];c,s=math.cos(angle),math.sin(angle);rot=np.array([[c,-s,0],[s,c,0],[0,0,1]])
    new['route_scaled_asset_ned']=((p[:,[1,0,2]]*np.array([1,1,-1])-new['cave_offset_ned'])@rot).tolist()
    out=root/'porth-survey-v5';out.mkdir();(out/'plan.json').write_text(json.dumps(new,indent=2)+'\n')
    # A fresh-process end-of-passage calibration, through the same scene/dynamics.
    q=p[max(0,lo-32):lo+33];heading=yaw[max(0,lo-32):lo+33]
    cal=dict(new,version='porth-survey-v6',route_enu=q.tolist(),route_yaw_enu=heading.tolist(),spawn_enu=q[0].tolist(),
     spawn_yaw_enu_deg=float(np.degrees(heading[0])),route_length_m=float(np.linalg.norm(np.diff(q,axis=0),axis=1).sum()),
     scope='Fresh-process main-end reversal calibration only; not full cave')
    cal['route_scaled_asset_ned']=((q[:,[1,0,2]]*np.array([1,1,-1])-cal['cave_offset_ned'])@rot).tolist()
    out=root/'porth-survey-v6';out.mkdir();(out/'plan.json').write_text(json.dumps(cal,indent=2)+'\n')
    print('turn old',turn,'trim',lo,hi,'new length',new['route_length_m'],'calibration',cal['route_length_m'],'spawn',cal['spawn_enu'],'yaw',cal['spawn_yaw_enu_deg'])


if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument("plans_root");revise(parser.parse_args().plans_root)
