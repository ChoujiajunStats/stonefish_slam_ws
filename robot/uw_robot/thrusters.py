"""Locked model geometry; wrench about the measured physical CG, expressed in FLU."""
import hashlib
import math
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
import yaml
from uw_robot.frames import frd_to_flu, rotate, rpy_quaternion


def extract_profile(path):
    path=Path(path)
    robot=ET.parse(path).find('robot')
    items=[]
    for a in robot.findall('actuator'):
        if a.get('type')!='thruster': continue
        origin=a.find('origin'); spec=a.find('specs'); prop=a.find('propeller')
        xyz=list(map(float,origin.get('xyz').split())); rpy=list(map(float,origin.get('rpy').split()))
        kt=list(map(float,spec.get('thrust_coeff').split()))
        if len(kt)==1:kt=kt*2
        items.append(dict(name=a.get('name'),position_frd=xyz,rpy_frd=rpy,
            axis_frd=list(rotate(rpy_quaternion(*rpy),(1,0,0))),inverted=spec.get('inverted')=='true',
            right_handed=prop.get('right')=='true',diameter_m=float(prop.get('diameter')),
            max_rpm=float(spec.get('max_rpm')),kt_forward=kt[0],kt_reverse=kt[1],kq=float(spec.get('torque_coeff'))))
    return {'schema_version':1,'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'density_kg_m3':1031.0,'wrench_reference':'physical_CG','wrench_frame':'FLU',
            'velocity_reference':'base_link_origin','setpoint_limit':0.6,'thrusters':items}


def load_profile(path):
    p=yaml.safe_load(Path(path).read_text());names=[x['name'] for x in p['thrusters']]
    expected=6 if p.get('variant')=='bluerov2_six_disaware' else 8
    if len(names)!=expected or len(set(names))!=expected:raise ValueError('Unexpected or duplicate thrusters')
    axes=p.get('controlled_axes',list(range(6)))
    if axes!=([0,1,2,3,5] if expected==6 else list(range(6))):raise ValueError('Invalid controlled axes')
    if not math.isfinite(p['density_kg_m3']) or p['density_kg_m3']<=0 or not 0<p['setpoint_limit']<=0.6:raise ValueError('Invalid fluid or setpoint limit')
    for t in p['thrusters']:
        if not all(math.isfinite(t[k]) and t[k]>0 for k in ('max_rpm','diameter_m','kt_forward','kt_reverse','kq')):raise ValueError('Invalid thruster coefficients')
        if t['kt_forward']!=t['kt_reverse']:raise ValueError('Asymmetric inverse mapping not implemented')
        if expected==6 and (not math.isfinite(t['rotor_time_constant_sec']) or t['rotor_time_constant_sec']<=0):raise ValueError('Invalid rotor time constant')
    return p


class Allocation:
    """Bounded weighted least squares; static bollard approximation with reaction torque."""
    def __init__(self,profile,model):
        self.profile=profile;self.names=[x['name'] for x in profile['thrusters']]
        if self.names!=model['names']:raise ValueError('Native channel order mismatch')
        cg=np.asarray(model['cg_frd_m'],dtype=float)*[1,-1,-1]
        columns=[];self.k=[];self.native_sign=[]
        for i,t in enumerate(profile['thrusters']):
            actual=model['geometry'][i]
            if not np.allclose(np.asarray(actual['position_frd'],dtype=float),t['position_frd'],atol=1e-7) or not np.allclose(np.asarray(actual['axis_frd'],dtype=float),t['axis_frd'],atol=1e-7):
                raise ValueError('Native geometry mismatch')
            a=np.asarray(frd_to_flu(t['axis_frd']));r=np.asarray(frd_to_flu(t['position_frd']))-cg
            # Static Q/T ratio follows handedness; includes axial reaction torque.
            qratio=(-1 if t['right_handed'] else 1)*t['diameter_m']*t['kq']/t['kt_forward']
            columns.append(np.r_[a,np.cross(r,a)+qratio*a])
            self.k.append(profile['density_kg_m3']*t['diameter_m']**4*t['kt_forward']*(t['max_rpm']/60)**2)
            self.native_sign.append((-1 if t['inverted'] else 1)*(1 if t['right_handed'] else -1))
        self.matrix=np.asarray(columns).T;self.k=np.array(self.k);self.native_sign=np.array(self.native_sign)
        self.controlled_axes=profile.get('controlled_axes',list(range(6)))
        self.control_matrix=self.matrix[self.controlled_axes,:]
        self.full_singular_values=np.linalg.svd(self.matrix,compute_uv=False)
        self.singular_values=np.linalg.svd(self.control_matrix,compute_uv=False)
        if np.linalg.matrix_rank(self.control_matrix)!=len(self.controlled_axes) or self.singular_values[-1]<0.05:raise ValueError('Invalid allocation rank/conditioning')
        self.limit=self.k*profile['setpoint_limit']**2
        # Force and torque tracking scaled to similar authority.
        self.weight=np.diag(np.asarray([1,1,1,4,4,4])[self.controlled_axes]);self.weighted=self.weight@self.control_matrix
        self.pinv=np.linalg.pinv(self.weighted)
        self.step=1/(np.linalg.norm(self.weighted,2)**2+1e-9)

    def allocate(self,wrench):
        w=np.asarray(wrench,dtype=float)
        if w.shape!=(6,) or not np.isfinite(w).all():raise ValueError('Nonfinite wrench')
        target=self.weight@w[self.controlled_axes]; f=np.clip(self.pinv@target,-self.limit,self.limit)
        for _ in range(48):f=np.clip(f-self.step*(self.weighted.T@(self.weighted@f-target)),-self.limit,self.limit)
        native=self.native_sign*np.sign(f)*np.sqrt(np.abs(f)/self.k)
        return native,self.matrix@f,bool(np.any(np.abs(f)>=self.limit*0.999))

    def predict(self,native):
        n=np.asarray(native);f=self.native_sign*np.sign(n)*n*n*self.k
        return self.matrix@f
