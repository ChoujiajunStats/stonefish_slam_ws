"""Schema 2 explicitly enables M1. Schema 1 validation remains observation-only."""
import math
from pathlib import Path
import yaml
from uw_app.config import ConfigError,UniqueKeyLoader,validate_config

M1_KEYS={'control_mode','case_id','initial_rpy_enu_deg','fixed_fixture','evaluation_phase'}

def load_run_config(path):
    value=yaml.load(Path(path).read_text(),Loader=UniqueKeyLoader)
    if not isinstance(value,dict) or value.get('schema_version')!=2:return validate_config(value)
    expected={'schema_version','run_id','mode','backend','control_authority','namespace','robot_profile','scene_profile',
        'observation_profile','controller_profile','state_source','observation_access','use_sim_time','seed',
        'visualization','recording_profile','ros_domain_id','startup_timeout_sec','duration_sec'}|M1_KEYS
    if set(value)!=expected:raise ConfigError('M1 schema missing/unknown fields')
    if value['controller_profile']!='body_velocity_4d':raise ConfigError('Explicit M1 profile required')
    if value['control_mode'] not in ('body_velocity','actuator_probe'):raise ConfigError('Invalid M1 mode')
    if value['evaluation_phase'] not in ('diagnostic','tuning','formal','manual'):raise ConfigError('Invalid evaluation phase')
    if value['recording_profile'] not in ('debug','control','none'):raise ConfigError('Invalid recording profile')
    if not isinstance(value['case_id'],str) or not value['case_id'] or not all(c.isalnum() or c in '_-' for c in value['case_id']):raise ConfigError('Invalid case ID')
    if type(value['fixed_fixture']) is not bool or (value['fixed_fixture'] and value['control_mode']!='actuator_probe'):raise ConfigError('Only actuator probe may use fixed fixture')
    rpy=value['initial_rpy_enu_deg']
    if not isinstance(rpy,list) or len(rpy)!=3 or not all(type(x) in (int,float) and math.isfinite(x) for x in rpy):raise ConfigError('Invalid initial attitude')
    if abs(rpy[0])>10 or abs(rpy[1])>10 or abs(rpy[2])>180:raise ConfigError('Initial attitude outside M1 fixture envelope')
    base={k:v for k,v in value.items() if k not in M1_KEYS}
    base.update(schema_version=1,controller_profile='disabled',recording_profile='none')
    validate_config(base)
    return dict(value)
