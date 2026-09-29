"""Pure request validation. Received requests retain their original expiry downstream."""
import math


def validate_request(request,now_ns,clock_ns,run_id,source,token,generation,last_sequence,mode,names,limits):
    if request['run_id']!=run_id or request['source']!=source or request['token']!=token or request['generation']!=generation:
        return 'authorization_mismatch'
    if request['sequence']<=last_sequence:return 'replayed_sequence'
    age=now_ns-request['issued_ns']
    if age<0 or age>250_000_000:return 'expired_steady_request'
    intent=request.get('valid_until_ns',0)
    if intent and (intent<=now_ns or intent<request['issued_ns']):return 'expired_intent_deadline'
    if request['frame']!=request['expected_frame']:return 'wrong_frame'
    if clock_ns-request['stamp_ns']>250_000_000:return 'expired_ros_stamp'
    if request['stamp_ns']-clock_ns>50_000_000:return 'future_ros_stamp'
    values=request['twist']
    if len(values)!=6 or not all(math.isfinite(x) for x in values):return 'nonfinite_twist'
    if values[3]!=0 or values[4]!=0:return 'unsupported_roll_pitch_rate'
    if mode=='body_velocity':
        if request['names'] or request['setpoint']:return 'probe_in_velocity_mode'
        if any(abs(v)>lim for v,lim in zip([values[0],values[1],values[2],values[5]],limits)):return 'request_limit_exceeded'
    else:
        if any(values):return 'velocity_in_probe_mode'
        if request['names']!=names or len(request['setpoint'])!=len(names):return 'invalid_channels'
        if not all(math.isfinite(x) for x in request['setpoint']):return 'nonfinite_probe_setpoint'
        if any(abs(x)>0.15 for x in request['setpoint']):return 'request_limit_exceeded'
    return None
