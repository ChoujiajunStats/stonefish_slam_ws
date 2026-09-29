"""Explicit known-route sensor collection; distinct from estimated navigation."""
import hashlib,json,math,re,shutil
import yaml
from uw_app.config import ConfigError


def validate_survey(v):
    if v.get('control_state_source')!='ground_truth_debug':raise ConfigError('Survey feedback must be explicitly PRIVILEGED_DEBUG')
    if not re.fullmatch(r'porth-survey-v[0-9]+',v.get('survey_plan','')):raise ConfigError('Invalid survey plan identifier')
    if not re.fullmatch('[0-9a-f]{64}',v.get('survey_plan_sha256','')):raise ConfigError('Survey plan hash required')
    x=v.get('survey_max_distance_m')
    if type(x) not in (int,float) or not math.isfinite(x) or not 1<=x<=700:raise ConfigError('Invalid finite survey distance')
    if v.get('recording_profile') not in ('state','none'):raise ConfigError('Long survey uses bounded recording; images remain in SLAM DB')
    water=v.get('survey_water_jerlov',.22)
    if type(water) not in (int,float) or not math.isfinite(water) or not 0<=water<=1:raise ConfigError('Water Jerlov must be in [0,1]')


def prepare(out,cfg):
    source=out.parent.parent/'plans'/cfg['survey_plan']/'plan.json'
    if hashlib.sha256(source.read_bytes()).hexdigest()!=cfg['survey_plan_sha256']:raise ValueError('Survey plan hash mismatch')
    plan=json.loads(source.read_text());shutil.copy2(source,out/'survey-plan.json')
    if plan['asset_sha256']!=hashlib.sha256((out/'cave-asset.json').read_bytes()).hexdigest():raise ValueError('Survey asset mismatch')
    from uw_simulations.survey_scene import prepare as prepare_scene
    from uw_guard.configuration import route_safety_envelope
    prepare_scene(out/'m2.scn', out/'m2.assets.json', plan,
                  plan_sha256=cfg['survey_plan_sha256'], namespace=cfg['namespace'],
                  initial_yaw_enu_deg=cfg['initial_rpy_enu_deg'][2],
                  water_jerlov=cfg.get('survey_water_jerlov'))
    path=out/'guard-parameters.yaml'
    parameters=yaml.safe_load(path.read_text())
    parameters['safety_envelope'].update(route_safety_envelope(plan['route_enu']))
    path.write_text(yaml.safe_dump(parameters))
