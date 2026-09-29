"""Explicit estimated-feedback navigation mode; never inherited by older schemas."""
from pathlib import Path
import yaml
from uw_app.config import ConfigError,UniqueKeyLoader
from uw_app.m2_config import validate


def load_config(path):
    value=yaml.load(Path(path).read_text(),Loader=UniqueKeyLoader)
    if not isinstance(value,dict) or value.get('schema_version')!=4:raise ConfigError('M3 requires schema 4')
    if value.get('navigation_profile')!='local_waypoints' or value.get('task_profile')!='finite_mission':raise ConfigError('Explicit M3 profiles required')
    if value.get('estimator_profile')!='openvins_m3_static' or value.get('fixed_fixture') is not False or value.get('diagnostic_motion') is not False:raise ConfigError('M3 uses free-body estimated feedback only')
    porth=value.get('scene_profile')=='porth_sump9'
    survey=porth and value.get('survey_profile')=='known_route_capture_v1'
    extra=('cave_asset','slam_profile','execute_path') if porth else ()
    if survey:
        extra+=('survey_profile','survey_plan','survey_plan_sha256','control_state_source','survey_max_distance_m','survey_water_jerlov')
        from uw_app.survey import validate_survey
        validate_survey(value)
    if value.get('slam_profile')=='orbslam3_stereo' and not survey:raise ConfigError('ORB-SLAM3 initially requires the explicit truth-controlled survey profile')
    if porth:
        if value.get('cave_asset')!='porth_sump9_v1' or value.get('slam_profile') not in ('rtabmap_stereo','orbslam3_stereo'):raise ConfigError('Unknown imported cave or SLAM profile')
        if type(value.get('execute_path')) is not bool:raise ConfigError('Explicit path authorization boolean required')
        if value.get('execute_path') and value.get('evaluation_phase')=='manual':raise ConfigError('Manual launch never auto-arms')
        if value.get('evaluation_phase')=='formal':raise ConfigError('Porth is a separate SLAM demonstration, not frozen M3 acceptance')
        if value.get('case_id')!='manual' or (not survey and value.get('initial_rpy_enu_deg')!=[0.,0.,90.]):raise ConfigError('Porth uses the screened initial pose and demo runner')
    old={k:v for k,v in value.items() if k not in ('navigation_profile','task_profile',*extra)}
    if porth:old['scene_profile']='visual_fixture'
    old.update(schema_version=3,estimator_profile='openvins_m2');validate(old,maximum_duration=7200 if survey else 300)
    if value['scene_profile']!='visual_fixture' and not porth:raise ConfigError('M3 bounded navigation requires an explicitly validated scene')
    return value
