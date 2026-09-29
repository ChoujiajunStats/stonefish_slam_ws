"""Four velocity targets plus independent roll/pitch attitude feedback; no position hold."""
import math
import numpy as np


def rpy(q):
    x,y,z,w=q
    return np.array([math.atan2(2*(w*x+y*z),1-2*(x*x+y*y)),
                     math.asin(max(-1,min(1,2*(w*y-z*x)))),
                     math.atan2(2*(w*z+x*y),1-2*(y*y+z*z))])


class BodyController:
    def __init__(self,parameters,allocation):
        self.p=parameters;self.allocation=allocation;self.reset()

    def reset(self):
        self.integral=np.zeros(4);self.attitude_integral=np.zeros(2);self.previous=np.zeros(8)

    def update(self,target,velocity,angles,dt):
        if not 0<dt<=0.1 or not np.isfinite(np.r_[target,velocity,angles,dt]).all():
            self.reset();raise ValueError('Invalid state or simulation dt')
        error=np.asarray(target)-np.asarray(velocity)[[0,1,2,5]]
        attitude_error=-np.asarray(angles[:2])
        desired=np.zeros(6)
        desired[[0,1,2,5]]=np.asarray(self.p['velocity_kp'])*error+self.integral
        desired[2]+=self.p['buoyancy_feedforward_N']
        desired[3:5]=np.asarray(self.p['attitude_kp'])*attitude_error-np.asarray(self.p['attitude_kd'])*np.asarray(velocity[3:5])+self.attitude_integral
        clipped=np.clip(desired,-np.asarray(self.p['wrench_limits']),self.p['wrench_limits'])
        command,predicted,saturated=self.allocation.allocate(clipped)
        step=self.p['setpoint_rate_per_sec']*dt
        command=np.clip(command,self.previous-step,self.previous+step);self.previous=command
        predicted=self.allocation.predict(command)
        # Back calculation includes allocator and rate saturation; integral is force/torque.
        self.integral+=dt*(np.asarray(self.p['velocity_ki'])*error+3*(predicted-desired)[[0,1,2,5]])
        self.integral=np.clip(self.integral,-np.asarray(self.p['integral_force_limits']),self.p['integral_force_limits'])
        self.attitude_integral+=dt*(np.asarray(self.p['attitude_ki'])*attitude_error+3*(predicted-desired)[3:5])
        self.attitude_integral=np.clip(self.attitude_integral,-self.p['attitude_integral_limit'],self.p['attitude_integral_limit'])
        return command,desired,predicted,saturated or bool(np.any(clipped!=desired))
