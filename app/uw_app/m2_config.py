"""Explicit M2 schema; no mutation of schema 1/2 behavior."""
import math
from pathlib import Path
import yaml
from uw_app.config import ConfigError,UniqueKeyLoader,validate_config
from uw_app.m1_config import M1_KEYS


def load_config(path):
    v=yaml.load(Path(path).read_text(),Loader=UniqueKeyLoader)
    return validate(v)


def validate(v,maximum_duration=300):
    extras=M1_KEYS|{'diagnostic_motion','estimator_profile'}
    if not isinstance(v,dict) or v.get('schema_version')!=3:raise ConfigError('M2 requires schema 3')
    if v.get('state_source')!='openvins_stereo_imu' or v.get('estimator_profile')!='openvins_m2':raise ConfigError('M2 needs explicit OpenVINS state source')
    if v.get('scene_profile') not in ('empty_water','visual_fixture'):raise ConfigError('Unknown M2 scene')
    if v.get('recording_profile') not in ('state','sensors','debug','none'):raise ConfigError('Unknown M2 recording profile')
    if v.get('control_mode')!='body_velocity' or v.get('controller_profile')!='body_velocity_4d':raise ConfigError('M2 diagnostic controller must reuse M1')
    if type(v.get('diagnostic_motion')) is not bool or type(v.get('fixed_fixture')) is not bool:raise ConfigError('Fixture flags must be boolean')
    if v['fixed_fixture'] and v['diagnostic_motion']:raise ConfigError('A fixed calibration fixture cannot run motion control')
    if v.get('evaluation_phase') not in ('manual','diagnostic','tuning','formal'):raise ConfigError('Invalid phase')
    if not isinstance(v.get('case_id'),str) or not v['case_id'].replace('_','').isalnum():raise ConfigError('Invalid case ID')
    if v['evaluation_phase']=='manual' and (v['diagnostic_motion'] or v['fixed_fixture']):raise ConfigError('Manual launch never auto-arms or fixes the robot')
    rpy=v.get('initial_rpy_enu_deg')
    if not isinstance(rpy,list) or len(rpy)!=3 or not all(type(x) in (int,float) and math.isfinite(x) for x in rpy):raise ConfigError('Invalid initial attitude')
    if max(abs(rpy[0]),abs(rpy[1]))>10 or abs(rpy[2])>180:raise ConfigError('Initial attitude outside fixture limits')
    base={k:x for k,x in v.items() if k not in extras}
    base.update(schema_version=1,state_source='ground_truth_debug',controller_profile='disabled',scene_profile='empty_water',recording_profile='none')
    validate_config(base)
    if not extras.issubset(v):raise ConfigError('Missing M2 fields')
    if v['duration_sec']>maximum_duration:raise ConfigError('Finite run duration exceeds explicit profile limit')
    return v
