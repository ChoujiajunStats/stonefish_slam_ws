"""Survey optical fixtures; no forces, sensor preprocessing or motor commands."""
import math
import xml.etree.ElementTree as ET


def apply_optics(root, settings, namespace):
    jerlov=settings['jerlov']
    if not isinstance(jerlov,(int,float)) or not math.isfinite(jerlov) or not 0<=jerlov<=1:
        raise ValueError('Native Jerlov parameter must be finite in [0,1]')
    root.find('environment/ocean/water').set('jerlov',str(jerlov))
    if settings['lighting']!='robot_spots':raise ValueError('Unsupported survey optical fixture')
    robot=root.find('robot');link=robot.find('base_link').get('name')
    for light in list(root.findall('light')):
        if light.get('name','').startswith('porth_'):root.remove(light)
    for side in (-1,1):
        light=ET.SubElement(robot,'light',name=f'survey_camera_lamp_{side}')
        ET.SubElement(light,'specs',illuminance=str(settings['native_flux_each']),radius='.025',cone_angle='110')
        ET.SubElement(light,'color',temperature='5000')
        ET.SubElement(light,'link',name=link)
        # Native FRD: offset from the stereo lenses, +Z spotlight axis rotated
        # onto +X. Cameras remain at their original calibrated transforms.
        ET.SubElement(light,'origin',xyz=f'0.20 {side*.23} 0.05',rpy=f'0 {math.pi/2} {side*.05}')
    return dict(**settings,count=2,cone_deg=110,temperature_k=5000,
        sensor_postprocessing='NONE',native_blur_shader='NOT_ENABLED_IN_PINNED_VERSION',
        dynamics_changed=False,calibrated_real_water=False)
