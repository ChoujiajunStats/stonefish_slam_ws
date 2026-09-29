"""Stonefish survey geometry and optics; accepts an already locked route plan."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def prepare(scene_path, evidence_path, plan, *, plan_sha256, namespace,
            initial_yaw_enu_deg, water_jerlov=None):
    scene_path, evidence_path = Path(scene_path), Path(evidence_path)
    if plan['clearance_lower_bound_m']<.80 or len(plan['lights_enu'])>32:raise ValueError('Invalid screened route or native light count')
    tree=ET.parse(scene_path);root=tree.getroot()
    x,y,z=plan['spawn_enu']
    root.find('robot/world_transform').set('xyz',f'{y} {x} {-z}')
    if abs(initial_yaw_enu_deg-plan.get('spawn_yaw_enu_deg',90.))>1e-5:raise ValueError('Survey initial heading mismatch')
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
        if water_jerlov is not None:settings['jerlov']=water_jerlov
        optics=apply_optics(root,settings,namespace)
    elif water_jerlov is not None:raise ValueError('Water override requires an explicit optical survey plan')
    ET.indent(tree,space='  ');tree.write(scene_path,encoding='utf-8',xml_declaration=True)
    path=evidence_path;evidence=json.loads(path.read_text())
    evidence.update(scene_sha256=hashlib.sha256((scene_path).read_bytes()).hexdigest(),
        survey_plan_sha256=plan_sha256,cave_scale=plan['scale'],cave_offset_ned=plan['cave_offset_ned'],lighting=dict(type='STATIC_DIAGNOSTIC_POINT_LIGHTS',count=len(plan['lights_enu']),native_illuminance=plan['light_native_illuminance']))
    if optics:evidence.update(lighting=optics,jerlov=optics['jerlov'])
    path.write_text(json.dumps(evidence,indent=2)+'\n')
