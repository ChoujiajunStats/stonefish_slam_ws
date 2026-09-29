"""Import immutable Porth assets and derive a short, surface-screened demo route.

Run inside the project image. Original mesh geometry and textures are preserved.
The cropped roofless mesh is ONLY for RViz; physics uses the complete collision OBJ.
"""
import argparse,csv,json,math,shutil
from pathlib import Path
import numpy as np
from uw_simulations.scene import sha256


def read_obj(path):
    vertices=[];faces=[]
    with Path(path).open() as f:
        for line in f:
            if line.startswith('v '):vertices.append([float(x) for x in line.split()[1:4]])
            elif line.startswith('f '):
                face=[int(x.split('/')[0])-1 for x in line.split()[1:]]
                if min(face)<0:raise ValueError('Negative OBJ indices unsupported')
                faces.extend((face[0],face[i],face[i+1]) for i in range(1,len(face)-1))
    return np.array(vertices),np.array(faces,dtype=np.int32)


def surface_distance(point,triangles):
    """Exact point-to-triangle minimum, including edges, for the imported mesh."""
    a,b,c=triangles[:,0],triangles[:,1],triangles[:,2]
    u=b-a;v=c-a;w=point-a
    uu=np.einsum('ij,ij->i',u,u);uv=np.einsum('ij,ij->i',u,v);vv=np.einsum('ij,ij->i',v,v)
    wu=np.einsum('ij,ij->i',w,u);wv=np.einsum('ij,ij->i',w,v)
    den=uu*vv-uv*uv;valid=den>1e-18;safe=np.where(valid,den,1)
    s=(wu*vv-wv*uv)/safe;t=(wv*uu-wu*uv)/safe
    inside=valid&(s>=0)&(t>=0)&(s+t<=1)
    projection=a+s[:,None]*u+t[:,None]*v
    distance=np.where(inside,np.linalg.norm(point-projection,axis=1),np.inf)
    for x,y in ((a,b),(b,c),(c,a)):
        e=y-x;d=np.einsum('ij,ij->i',e,e)
        fraction=np.clip(np.einsum('ij,ij->i',point-x,e)/np.maximum(d,1e-18),0,1)
        distance=np.minimum(distance,np.linalg.norm(point-(x+fraction[:,None]*e),axis=1))
    return float(distance.min())


def crop_visual(source,output,origin,radius=8.):
    """Preserve OBJ UVs while removing distant surfaces and the RViz ceiling."""
    vertices=[];texcoords=[];normals=[];faces=[]
    with Path(source).open() as f:
        for line in f:
            if line.startswith('v '):vertices.append([float(x) for x in line.split()[1:4]])
            elif line.startswith('vt '):texcoords.append(line)
            elif line.startswith('vn '):normals.append(line)
            elif line.startswith('f '):
                indices=line.split()[1:];xyz=np.array([vertices[int(x.split('/')[0])-1] for x in indices])
                center=xyz.mean(axis=0)
                if np.linalg.norm(center[:2]-origin[:2])<radius and center[2]>=origin[2]-.15:faces.append(indices)
    used=[sorted({int(x.split('/')[i]) for face in faces for x in face if len(x.split('/'))>i and x.split('/')[i]}) for i in range(3)]
    maps=[{n:i+1 for i,n in enumerate(ids)} for ids in used]
    with Path(output).open('w') as f:
        f.write('mtllib porth.mtl\nusemtl rock\n')
        for i in used[0]:f.write('v '+' '.join(map(str,vertices[i-1]))+'\n')
        for i in used[1]:f.write(texcoords[i-1])
        for i in used[2]:f.write(normals[i-1])
        for face in faces:
            f.write('f '+' '.join('/'.join(str(maps[k][int(n)]) if n else '' for k,n in enumerate(x.split('/'))) for x in face)+'\n')
    return dict(vertices=len(used[0]),faces=len(faces),radius_source_units=radius,roof_cut_ned_z=float(origin[2]-.15))


def import_assets(source,output,upstream):
    source=Path(source);out=Path(output)
    if out.exists():raise ValueError('Asset directory already exists; select a new version, never overwrite')
    out.mkdir(parents=True)
    files={'visual.obj':'converted/porth_yr_ogof_sump9_visual.obj','collision.obj':'collision/porth_yr_ogof_sump9_collision.obj',
           'albedo.png':'converted/porth_yr_ogof_sump9_albedo.png','navigation_centerline.csv':'metadata/porth_yr_ogof_sump9_navigation_centerline.csv',
           'source-metadata.yaml':'metadata/porth_yr_ogof_sump9.yaml','source-inspection.json':'metadata/porth_yr_ogof_sump9_inspection.json'}
    origins={}
    for target,relative in files.items():
        shutil.copy2(source/relative,out/target);origins[target]=dict(relative_source=relative,sha256=sha256(out/target))
    (out/'porth.mtl').write_text('newmtl rock\nKa 1 1 1\nKd 1 1 1\nKs 0 0 0\nmap_Kd albedo.png\n')
    vertices,faces=read_obj(out/'collision.obj');triangles=vertices[faces]
    rows=list(csv.DictReader((out/'navigation_centerline.csv').open()))
    points=np.array([[float(r[k]) for k in ('north_m','east_m','down_m')] for r in rows]);chain=np.array([float(r['chainage_m']) for r in rows])
    scale=1.5
    # First preview uses a short route, no autonomous exploration or avoidance.
    goals=[[.8,0,0,0],[1.6,.12,0,.06],[2.4,.25,0,.10],[1.2,.12,0,.04],[0,0,0,0]]
    samples=[];last=np.zeros(3)
    for goal in goals:
        target=np.array(goal[:3]);samples.extend(last+(target-last)*v for v in np.linspace(0,1,25));last=target
    samples=np.array(samples);best=None
    for i in range(24,min(len(points)-16,240),12):
        direction=points[i+4,:2]-points[i,:2];heading=math.atan2(direction[1],direction[0]);c,s=math.cos(heading),math.sin(heading)
        body_to_ned=np.array([[c,-s,0],[s,c,0],[0,0,-1]])
        path=points[i]+samples@body_to_ned.T/scale
        # Distance is Lipschitz: subtract the maximum half sample interval.
        distances=[surface_distance(p,triangles)*scale for p in path[::4]]
        score=min(distances)-.11
        if best is None or score>best[0]:best=(score,i,heading,path)
    clearance,i,heading,path=best
    if clearance<.75:raise ValueError(f'No route with 0.75 m center-to-surface screening clearance: {clearance}')
    origin=points[i];c,s=math.cos(-heading),math.sin(-heading);rotation=np.array([[c,-s,0],[s,c,0],[0,0,1]])
    spawn=np.array([0.,0.,8.]);offset=spawn-scale*rotation@origin
    crop=crop_visual(out/'visual.obj',out/'rviz_cutaway.obj',origin)
    # Body OBJ is already in metres. Add a material reference for RViz/Assimp.
    robot=out/'bluerov2';robot.mkdir()
    for name in ('bluerov2.obj','bluerov2_wings.obj','cw.obj','ccw.obj','br2.png'):
        shutil.copy2(Path(upstream)/'data/bluerov2'/name,robot/name)
    for name in ('bluerov2.obj','bluerov2_wings.obj'):
        p=robot/name;original=p.read_text();p.write_text('mtllib robot.mtl\nusemtl '+('body' if name=='bluerov2.obj' else 'black')+'\n'+original)
    (robot/'robot.mtl').write_text('newmtl body\nKd 1 1 1\nmap_Kd br2.png\nnewmtl black\nKd 0.05 0.05 0.05\n')
    shutil.copy2(Path(upstream)/'scenarios/bluerov2.scn',robot/'source.scn')
    license=Path(upstream)/'LICENSE'
    if license.exists():shutil.copy2(license,robot/'LICENSE')
    report=dict(version='porth_sump9_v1',source=str(source),source_files=origins,scale=scale,
        scale_status='EXPERIMENTAL_NOT_SURVEY_CALIBRATION',original_bounds_ned=[vertices.min(axis=0).tolist(),vertices.max(axis=0).tolist()],
        cave_yaw_ned=-heading,cave_offset_ned=offset.tolist(),spawn_enu=[0.,0.,-8.],initial_yaw_enu_deg=90.,
        selected_chainage_source=float(chain[i]),selected_origin_source=origin.tolist(),waypoints_mission_start=goals,
        route_center_to_collision_surface_lower_bound_m=clearance,robot_screening_radius_m=.50,
        clearance_scope='Short prescribed polyline only; unsigned distance, not closed-volume topology certification',rviz_crop=crop,
        files_sha256={str(p.relative_to(out)):sha256(p) for p in out.rglob('*') if p.is_file()})
    (out/'asset.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True);p.add_argument('--upstream',default='/opt/uw_underlay/share/stonefish_bluerov2');a=p.parse_args();import_assets(a.source,a.output,a.upstream)


if __name__=='__main__':main()
