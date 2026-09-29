"""Finite polyline following. State provenance is supplied by the caller."""
import math
from uw_navigation.core import body_error,guide,wrap,yaw


class Follower:
    def __init__(self,points,speed=.20,headings=None):
        if len(points)<2 or not all(len(p)==3 and all(math.isfinite(x) for x in p) for p in points):raise ValueError('Invalid polyline')
        if headings is not None and (len(headings)!=len(points) or not all(math.isfinite(x) for x in headings)):raise ValueError('Invalid view headings')
        # Consecutive duplicate vertices carry no additional route distance.
        keep=[0]+[i for i in range(1,len(points)) if math.dist(points[i],points[i-1])>1e-8]
        points=[points[i] for i in keep]
        self.headings=[headings[i] for i in keep] if headings is not None else None
        self.turns=[]
        for i in range(1,len(points)-1):
            a=[points[i][k]-points[i-1][k] for k in range(3)]
            b=[points[i+1][k]-points[i][k] for k in range(3)]
            if sum(x*y for x,y in zip(a,b))<-.5*math.sqrt(sum(x*x for x in a)*sum(x*x for x in b)):self.turns.append(i)
        self.turns.append(len(points)-1);self.leg=0
        self.points=points;self.index=0;self.arc=[0.]
        for a,b in zip(points[:-1],points[1:]):self.arc.append(self.arc[-1]+math.dist(a,b))
        self.p=dict(position_gain=1.0,yaw_gain=.8,horizontal_speed_m_s=speed,vertical_speed_m_s=.08,yaw_rate_rad_s=.18)
    def update(self,position,q):
        stop=self.turns[self.leg]
        if self.leg<len(self.turns)-1 and math.dist(position,self.points[stop])<.10:
            self.index=stop;self.leg+=1;stop=self.turns[self.leg]
        end=min(stop+1,self.index+6)
        nearest=min(range(self.index,end),key=lambda i:math.dist(position,self.points[i]))
        self.index=nearest
        target=min(stop,self.index+2)
        a=self.points[max(0,target-2)];b=self.points[target]
        angle=self.headings[target] if self.headings is not None else math.atan2(b[1]-a[1],b[0]-a[0])
        command,distance,error=guide(position,q,b,angle,self.p)
        vector,_=body_error(position,q,b)
        raw=[self.p['position_gain']*x for x in vector]
        common=min(1.,self.p['horizontal_speed_m_s']/max(math.hypot(*raw[:2]),1e-12),self.p['vertical_speed_m_s']/max(abs(raw[2]),1e-12))
        command[:3]=[x*common for x in raw]
        scale=max(0.,1-abs(error)/.6)
        command[:3]=[x*scale for x in command[:3]]
        cross=math.dist(position,self.points[self.index])
        complete=self.index>=len(self.points)-3 and math.dist(position,self.points[-1])<.18
        return command,dict(index=self.index,progress_m=self.arc[self.index],remaining_m=self.arc[-1]-self.arc[self.index],
            cross_track_m=cross,yaw_error_rad=error,complete=complete,target=b)
