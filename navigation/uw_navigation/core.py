"""Bounded local waypoint guidance; no simulator, actuator or truth dependencies."""
import math


def wrap(x):return math.atan2(math.sin(x),math.cos(x))


def yaw(q):
    x,y,z,w=q
    return math.atan2(2*(w*z+x*y),1-2*(y*y+z*z))


def body_error(position,quaternion,target):
    x,y,z,w=quaternion
    if not all(math.isfinite(v) for v in [*position,*quaternion,*target]) or abs(sum(v*v for v in quaternion)-1)>1e-4:
        raise ValueError('Invalid state')
    # Hamilton body->odom rotation, transposed to transform the numerical vector.
    r=((1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)),
       (2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)),
       (2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)))
    e=[b-a for a,b in zip(position,target)]
    return [sum(r[j][i]*e[j] for j in range(3)) for i in range(3)],math.sqrt(sum(v*v for v in e))


def guide(position,quaternion,target,target_yaw,p):
    error,distance=body_error(position,quaternion,target)
    velocity=[p['position_gain']*v for v in error]
    norm=math.hypot(*velocity[:2]);scale=min(1,p['horizontal_speed_m_s']/max(norm,1e-12))
    velocity[:2]=[v*scale for v in velocity[:2]]
    velocity[2]=max(-p['vertical_speed_m_s'],min(p['vertical_speed_m_s'],velocity[2]))
    angle=wrap(target_yaw-yaw(quaternion))
    rate=max(-p['yaw_rate_rad_s'],min(p['yaw_rate_rad_s'],p['yaw_gain']*angle))
    return velocity+[rate],distance,angle


def validate_waypoints(run,expected,mission,authorize,points,timeout,frame,p):
    if run!=expected:return 'wrong_run'
    if not authorize:return 'explicit_arm_authorization_required'
    if not mission or len(mission)>64 or not mission.replace('_','').replace('-','').isalnum():return 'invalid_mission_id'
    if not math.isfinite(timeout) or not 1<=timeout<=p['maximum_timeout_sec']:return 'invalid_timeout'
    if not 1<=len(points)<=p['maximum_waypoints']:return 'invalid_waypoint_count'
    for f,xyz,q in points:
        if f not in ([frame] if isinstance(frame,str) else frame):return 'wrong_frame'
        if not all(math.isfinite(v) for v in xyz+q):return 'nonfinite_waypoint'
        if max(abs(xyz[0]),abs(xyz[1]))>p['horizontal_goal_abs_m'] or abs(xyz[2])>p['vertical_goal_abs_m']:return 'goal_outside_local_envelope'
        if abs(sum(v*v for v in q)-1)>1e-4 or abs(q[0])+abs(q[1])>1e-6:return 'nonhorizontal_or_invalid_orientation'
    return None


def relative_goal(xyz,angle,origin,origin_yaw):
    c,s=math.cos(origin_yaw),math.sin(origin_yaw)
    return [origin[0]+c*xyz[0]-s*xyz[1],origin[1]+s*xyz[0]+c*xyz[1],origin[2]+xyz[2]],wrap(origin_yaw+angle)
