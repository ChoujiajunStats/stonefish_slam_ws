"""Offline branch derivation used for survey v2; fixed metric geometry and deterministic A*."""
import heapq,json,math
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from scipy.ndimage import label
from uw_simulations.surface import SurfaceQuery
from uw_simulations.porth_assets import read_obj,surface_distance
def derive(directory,output):
 v,f=read_obj(Path(directory)/'collision.obj');tri=v[f]*1.5;surface=SurfaceQuery(tri)
 regions=[([-39,11,-3],[-23,30,4],[-36.5,12,.45],[-28,28,.45]),([-35,-5,-3],[-19,4,4],[-34,-2,.45],[-21,0,.45]),([39,-13,-3],[50,11,4],[41,-11,.45],[42,8,.45])]
 for no,(lo,hi,start,goal) in enumerate(regions):
  lo=np.array(lo,float);hi=np.array(hi,float);spacing=.2
  t=tri[np.all((tri.max(axis=1)>lo-2)&(tri.min(axis=1)<hi+2),axis=1)];samples=[]
  for a,b,c in t:
   n=max(1,math.ceil(max(np.linalg.norm(a-b),np.linalg.norm(a-c),np.linalg.norm(b-c))/.10))
   i,j=np.indices((n+1,n+1));mask=i+j<=n;i=i[mask]/n;j=j[mask]/n;samples.extend(a+i[:,None]*(b-a)+j[:,None]*(c-a))
  tree=cKDTree(np.array(samples));axes=[np.arange(a,b+spacing/2,spacing) for a,b in zip(lo,hi)]
  grid=np.stack(np.meshgrid(*axes,indexing='ij'),axis=-1);d=tree.query(grid.reshape(-1,3),workers=4)[0].reshape(grid.shape[:-1]);side=surface.signed(grid.reshape(-1,3)).reshape(grid.shape[:-1]);free=(d>.95)&(side>.90)
  si=tuple(np.round((np.array(start)-lo)/spacing).astype(int));gi=np.round((np.array(goal)-lo)/spacing).astype(int)
  comp,n=label(free);seed=comp[si];print('branch',no,'seed',seed,'components',n,flush=True)
  if not seed:raise ValueError('badseed')
  reachable=np.argwhere(comp==seed);goal_index=tuple(reachable[np.argmin(np.linalg.norm((reachable-gi)*spacing,axis=1))]);print('goal',grid[goal_index], 'off',np.linalg.norm(grid[goal_index]-goal),flush=True)
  frontier=[(0.,si)];cost={si:0.};prev={};steps=[np.eye(3,dtype=int)[i]*s for i in range(3) for s in (-1,1)]
  while frontier:
   _,u=heapq.heappop(frontier)
   if u==goal_index:break
   for step in steps:
    w=tuple(np.array(u)+step)
    if any(x<0 or x>=free.shape[i] for i,x in enumerate(w)) or not free[w]:continue
    c=cost[u]+spacing*(1+.1/max(.1,d[w]-.8))
    if c<cost.get(w,float('inf')):
     cost[w]=c;prev[w]=u;heapq.heappush(frontier,(c+np.linalg.norm((np.array(w)-goal_index)*spacing),w))
  chain=[goal_index]
  while chain[-1]!=si:chain.append(prev[chain[-1]])
  p=np.array([grid[q] for q in chain[::-1]]);p=np.vstack([start,p]);np.save(str(Path(output)/('branch-safe-'+str(no)+'.npy')),p)
  print('length',np.linalg.norm(np.diff(p,axis=0),axis=1).sum(),'exactmin',min(surface_distance(q,t) for q in p),flush=True)
