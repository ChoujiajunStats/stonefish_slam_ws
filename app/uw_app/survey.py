"""Explicit known-route sensor collection; distinct from estimated navigation."""
import hashlib,json,math,re,shutil
from pathlib import Path
import xml.etree.ElementTree as ET
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
    if plan['clearance_lower_bound_m']<.80 or len(plan['lights_enu'])>32:raise ValueError('Invalid screened route or native light count')
    tree=ET.parse(out/'m2.scn');root=tree.getroot()
    x,y,z=plan['spawn_enu']
    root.find('robot/world_transform').set('xyz',f'{y} {x} {-z}')
    if abs(cfg['initial_rpy_enu_deg'][2]-plan.get('spawn_yaw_enu_deg',90.))>1e-5:raise ValueError('Survey initial heading mismatch')
    cave=root.find("static[@name='porth_sump9']")
    for mesh in cave.findall('./*/mesh'):mesh.set('scale',str(plan['scale']))
    cave.find('world_transform').set('xyz',' '.join(map(str,plan['cave_offset_ned'])))
    for light in list(root.findall('light')):
        if light.get('name','').startswith('porth_fixed_flood'):root.remove(light)
    for i,(x,y,z) in enumerate(plan['lights_enu']):
        lamp=ET.SubElement(root,'light',name='porth_survey_light_'+str(i))
        ET.SubElement(lamp,'specs',illuminance=str(plan['light_native_illuminance']),radius='.03')
        ET.SubElement(lamp,'color',temperature='4500')
        ET.SubElement(lamp,'world_transform',xyz=f'{y} {x} {-z}',rpy='0 0 0')
    optics=None
    if 'optics' in plan:
        from uw_simulations.optics import apply_optics
        if not Path('/opt/uw/survey-lock.sha256').exists():raise ValueError('Robot optical lights require the locked survey image')
        settings=dict(plan['optics'])
        if 'survey_water_jerlov' in cfg:settings['jerlov']=cfg['survey_water_jerlov']
        optics=apply_optics(root,settings,cfg['namespace'])
    elif 'survey_water_jerlov' in cfg:raise ValueError('Water override requires an explicit optical survey plan')
    ET.indent(tree,space='  ');tree.write(out/'m2.scn',encoding='utf-8',xml_declaration=True)
    p=out/'guard-parameters.yaml';guard=yaml.safe_load(p.read_text())
    route=plan['route_enu'];e=guard['safety_envelope']
    e.update(depth_enu_m=[min(x[2] for x in route)-1,max(x[2] for x in route)+1],
        horizontal_position_abs_m=max(abs(x) for p in route for x in p[:2])+2)
    p.write_text(yaml.safe_dump(guard))
    path=out/'m2.assets.json';evidence=json.loads(path.read_text())
    evidence.update(scene_sha256=hashlib.sha256((out/'m2.scn').read_bytes()).hexdigest(),
        survey_plan_sha256=cfg['survey_plan_sha256'],cave_scale=plan['scale'],cave_offset_ned=plan['cave_offset_ned'],lighting=dict(type='STATIC_DIAGNOSTIC_POINT_LIGHTS',count=len(plan['lights_enu']),native_illuminance=plan['light_native_illuminance']))
    if optics:evidence.update(lighting=optics,jerlov=optics['jerlov'])
    path.write_text(json.dumps(evidence,indent=2)+'\n')
