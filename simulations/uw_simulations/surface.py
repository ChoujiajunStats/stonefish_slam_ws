"""Oriented nearest-triangle query for offline inspection of open cave meshes.

This is a surface-side heuristic, not a watertight solid containment guarantee.
Positive side is checked against the known internal main centerline. Exact
unsigned clearance certification remains a separate calculation.
"""
import numpy as np
from scipy.spatial import cKDTree


class SurfaceQuery:
    def __init__(self,triangles):
        self.triangles=triangles;self.tree=cKDTree(triangles.mean(axis=1))
    def signed(self,points):
        results=[]
        for start in range(0,len(points),4000):
            q=np.asarray(points[start:start+4000]);_,idx=self.tree.query(q,k=24,workers=4)
            tri=self.triangles[idx];p=q[:,None,:];a,b,c=tri[:,:,0],tri[:,:,1],tri[:,:,2];u=b-a;v=c-a;w=p-a
            dot=lambda a,b:np.einsum('...i,...i->...',a,b)
            uu=dot(u,u);uv=dot(u,v);vv=dot(v,v);wu=dot(w,u);wv=dot(w,v)
            den=uu*vv-uv*uv;safe=np.maximum(den,1e-18);s=(wu*vv-wv*uv)/safe;t=(wv*uu-wu*uv)/safe
            inside=(den>1e-18)&(s>=0)&(t>=0)&(s+t<=1)
            d=np.where(inside,np.linalg.norm(p-a-s[...,None]*u-t[...,None]*v,axis=-1),np.inf)
            for x,y in ((a,b),(b,c),(c,a)):
                e=y-x;fraction=np.clip(dot(p-x,e)/np.maximum(dot(e,e),1e-18),0,1)
                d=np.minimum(d,np.linalg.norm(p-x-fraction[...,None]*e,axis=-1))
            nearest=np.argmin(d,axis=1);n=np.arange(len(q));sign=np.sign(dot(w,np.cross(u,v)))[n,nearest]
            results.extend(d[n,nearest]*sign)
        return np.array(results)
