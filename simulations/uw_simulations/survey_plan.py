"""Known-geometry, offline survey route. Never an online exploration planner."""
import argparse,csv,hashlib,json,math
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
from uw_simulations.porth_assets import read_obj,surface_distance
from uw_simulations.surface import SurfaceQuery


def resample(points,spacing=.15):
    result=[]
    for a,b in zip(points[:-1],points[1:]):
        result.extend(np.linspace(a,b,max(1,math.ceil(np.linalg.norm(b-a)/spacing))+1)[:-1])
    return np.array(result+[points[-1]])


def world(points,asset):
    angle=asset['cave_yaw_ned'];c,s=math.cos(angle),math.sin(angle)
    r=np.array([[c,-s,0],[s,c,0],[0,0,1]])
    ned=np.asarray(points)@r.T+asset['cave_offset_ned']
    return ned[:,[1,0,2]]*np.array([1,1,-1])


def build(directory,out):
    directory=Path(directory);out=Path(out);out.mkdir(parents=True,exist_ok=False)
    asset=json.loads((directory/'asset.json').read_text());scale=asset['scale']
    v,f=read_obj(directory/'collision.obj');tri=v[f]*scale
    rows=list(csv.DictReader((directory/'navigation_centerline.csv').open()))
    main=np.array([[float(r[k])*scale for k in ('north_m','east_m','down_m')] for r in rows])[:511]
    # These are inspected branch corridors in scaled asset N/E coordinates.
    # They are inputs to geometric screening, not alleged reconstructed paths.
    from uw_simulations.survey_branches import derive
    derive(directory,out)
    branches=[np.load(out/('branch-safe-'+str(i)+'.npy')) for i in range(3)]
    tmin=tri.min(axis=1);tmax=tri.max(axis=1);oriented=SurfaceQuery(tri)
    def improve(points):
        result=[]
        for p in points:
            local=tri[np.all((tmax>p-4)&(tmin<p+4),axis=1)]
            if surface_distance(p,local)<1.15:
                initial=max([p+np.array([0,0,z]) for z in np.linspace(-1.5,1.5,13)],key=lambda q:surface_distance(q,local))
                r=minimize(lambda q:-min(surface_distance(q,local),1.20)+.08*np.linalg.norm(q-p),initial,
                    method='Powell',bounds=[(p[0]-.6,p[0]+.6),(p[1]-.6,p[1]+.6),(p[2]-1.5,p[2]+1.5)],options={'maxiter':12,'xtol':.015})
                if surface_distance(r.x,local)>surface_distance(p,local):p=r.x
            result.append(p)
        return np.array(result)
    main=improve(main)
    # A* branch vertices are already screened. Smooth only with certified shortcuts.
    def simplify(b):
        result=[b[0]];i=0
        while i<len(b)-1:
            best=i+1
            for j in range(i+2,min(i+13,len(b))):
                pts=resample(np.array([b[i],b[j]]),.10)
                local=tri[np.all((tmax>pts.min(axis=0)-2)&(tmin<pts.max(axis=0)+2),axis=1)]
                if min(surface_distance(q,local) for q in pts)<.96 or min(oriented.signed(pts))<.90:break
                best=j
            result.append(b[best]);i=best
        return np.array(result)
    branches=[simplify(b) for b in branches]
    # Start at the previously screened spawn, visit the entry end, then each
    # branch on the outward traversal, and return down the main passage.
    start=120
    connections=[int(np.argmin(np.linalg.norm(main-b[0],axis=1))) for b in branches]
    tour=list(main[start::-1]);labels=['main_entry']*len(tour)
    for i,p in enumerate(main[1:],1):
        tour.append(p);labels.append('main_outward')
        for j,k in enumerate(connections):
            if k==i:
                b=branches[j];excursion=np.vstack([p,b,b[::-1],p])
                tour.extend(excursion);labels.extend(['branch_'+str(j+1)]*len(excursion))
    tour.extend(main[-2:start-1:-1]);labels.extend(['main_return']*(len(main)-start-1))
    # Certify every straight segment against collision triangles. The distance
    # function is 1-Lipschitz; subtracting half the spacing bounds the gaps.
    dense=resample(np.array(tour),.15)
    distances=[]
    for i,p in enumerate(dense):
        local=tri[np.all((tmax>p-4)&(tmin<p+4),axis=1)]
        distances.append(surface_distance(p,local))
    # The 1.5x source route has two narrow throats. The dedicated full-survey
    # scene uses 1.8x scale; no existing scene/asset is modified.
    ratio=1.8/scale;dense*=ratio;main*=ratio;branches=[b*ratio for b in branches]
    lower=float((min(distances)-.075)*ratio)
    asset=dict(asset);asset['scale']=1.8
    angle=asset['cave_yaw_ned'];c,s=math.cos(angle),math.sin(angle)
    rot=np.array([[c,-s,0],[s,c,0],[0,0,1]])
    asset['cave_offset_ned']=(np.array([0.,0.,8.])-1.8*rot@np.array(asset['selected_origin_source'])).tolist()
    print('points',len(dense),'clearance bound',lower,flush=True)
    if lower<.80:
        (out/'unsafe.json').write_text(json.dumps(dict(points=dense.tolist(),clearance=distances)))
        raise ValueError('Route clearance is insufficient; minimum at '+str(dense[np.argmin(distances)]))
    dense=dense[::-1].copy()
    enu=world(dense,asset);length=float(np.linalg.norm(np.diff(enu,axis=0),axis=1).sum())
    # 25 main lights plus one midpoint/tip per branch, below native 32 limit.
    arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(main,axis=0),axis=1))]
    lamps=np.array([main[np.argmin(abs(arc-x))] for x in np.linspace(0,arc[-1],25)]+[p for b in branches for p in (b[len(b)//2],b[-1])])
    from scipy.spatial import cKDTree
    signed_collision=SurfaceQuery(tri).signed(dense/ratio)
    vv,ff=read_obj(directory/'visual.obj')
    signed_visual=SurfaceQuery(vv[ff]*1.8).signed(dense)
    # Decimated collision faces contain local orientation disagreements;
    # the full visual mesh is the authoritative side check.
    if min(signed_visual)<=0:
        failure=dict(collision_min=float(min(signed_collision)),visual_min=float(min(signed_visual)),bad=[dict(index=int(i),point=dense[i].tolist(),collision=float(signed_collision[i]),visual=float(signed_visual[i])) for i in np.flatnonzero((signed_collision<=0)|(signed_visual<=0))])
        (out/'side-failure.json').write_text(json.dumps(failure,indent=2)+'\n')
        raise ValueError('Route leaves oriented interior surface side: '+str(failure)[:1000])
    references=[];headings=[]
    for line in [world(main,asset),*[world(b,asset) for b in branches]]:
        line=resample(line,.15)
        for i,point in enumerate(line):
            a=max(0,i-3);b=min(len(line)-1,i+3);delta=line[b]-line[a]
            if np.linalg.norm(delta[:2])<.01:
                a=max(0,i-12);b=min(len(line)-1,i+12);delta=line[b]-line[a]
            references.append(point);headings.append(math.atan2(delta[1],delta[0]))
    angles=np.array(headings)[cKDTree(references).query(enu)[1]]
    lamp_enu=world(lamps,asset);lamp_enu[:,2]+=.5
    result=dict(version=out.name,asset_sha256=hashlib.sha256((directory/'asset.json').read_bytes()).hexdigest(),
        scale=1.8,cave_offset_ned=asset['cave_offset_ned'],cave_yaw_ned=asset['cave_yaw_ned'],scale_status='EXPERIMENTAL_NOT_SURVEY_CALIBRATION',control_state_source='PRIVILEGED_DEBUG',
        slam_truth_input=False,route_enu=enu.tolist(),route_scaled_asset_ned=dense.tolist(),
        route_length_m=length,clearance_lower_bound_m=lower,clearance_sampling_m=.15*ratio,
        robot_screening_radius_m=.5,tracking_abort_m=.25,maximum_speed_m_s=.20,
        lights_enu=lamp_enu.tolist(),route_yaw_enu=angles.tolist(),spawn_yaw_enu_deg=90.,
        heading_policy='Canonical outward passage view retained during reverse travel',
        collision_orientation_disagreement_samples=int(sum(signed_collision<=0)),oriented_collision_side_min_m=float(min(signed_collision)*ratio),oriented_visual_side_min_m=float(min(signed_visual)),light_native_illuminance=1000000,
        main_enu=world(main,asset).tolist(),branches_enu=[world(b,asset).tolist() for b in branches],
        scope='Main passage round trip plus three screened branches; excludes last 16 centerline samples for visual standoff; branch tips stop at reachable interior',
        source_centerline_samples=527,used_main_samples=len(main),spawn_enu=asset['spawn_enu'])
    (out/'plan.json').write_text(json.dumps(result,indent=2)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(15,7));ax.scatter(v[::8,0]*1.8,v[::8,1]*1.8,s=.1,c='gray',label='Known asset')
    ax.plot(dense[:,0],dense[:,1],lw=1,c='blue',label='Screened prescribed route')
    ax.scatter(lamps[:,0],lamps[:,1],c='orange',s=15,label='Static diagnostic lights');ax.axis('equal');ax.legend()
    ax.set(xlabel='Scaled source N (m)',ylabel='Scaled source E (m)',title=f'{length:.1f} m tour, certified center clearance >= {lower:.2f} m')
    fig.tight_layout();fig.savefig(out/'route.png',dpi=160)
    print(json.dumps({k:x for k,x in result.items() if k not in ('route_enu','route_scaled_asset_ned','lights_enu','main_enu','branches_enu')}))


def main():
    p=argparse.ArgumentParser();p.add_argument('asset');p.add_argument('output');a=p.parse_args();build(a.asset,a.output)


if __name__=='__main__':main()
