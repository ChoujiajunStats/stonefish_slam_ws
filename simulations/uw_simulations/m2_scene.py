"""Explicit M2 sensor/visual fixture; original free-body hydrodynamics unchanged."""
import hashlib,json,math,random,struct,zlib
from pathlib import Path
import xml.etree.ElementTree as ET
import yaml
from uw_simulations.scene import sha256
from uw_perception.contracts import intrinsics


def texture(path, seed, size=1024):
    """Reproducible calibration texture, generated mathematically (no external assets)."""
    rng=random.Random(seed)
    cells=[[rng.choice((24,70,130,190,240)) for _ in range(size//16)] for _ in range(size//16)]
    rows=b''.join(b'\0'+bytes(cells[y//16][x//16] for x in range(size)) for y in range(size))
    def chunk(tag,data):return struct.pack('!I',len(data))+tag+data+struct.pack('!I',zlib.crc32(tag+data)&0xffffffff)
    Path(path).write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!2I5B',size,size,8,0,0,0,0))+chunk(b'IDAT',zlib.compress(rows))+chunk(b'IEND',b''))


def generate_m2_scene(upstream,template,profile,namespace,output,assets,config,session,mapping):
    from uw_simulations.m1_scene import generate_m1_scene
    evidence=generate_m1_scene(upstream,template,profile,namespace,output,assets,config,session,mapping)
    tree=ET.parse(output);root=tree.getroot();robot=root.find('robot')
    for sensor in robot.findall('sensor'):
        name=sensor.get('name')
        if name=='imu_filter':
            sensor.set('rate','100.0');sensor.set('uw_specific_force','true')
            sensor.find('noise').attrib.update(angle='0',angular_velocity='0.0002',linear_acceleration='0.01')
        elif name.startswith('camera_'):
            sensor.set('rate','-1');sensor.set('uw_capture_time','true')
    fixture_assets={}
    if config['scene_profile']=='visual_fixture':
        # Diagnostic scenery only: original robot mass/buoyancy/drag are untouched.
        for index,(position,dimensions) in enumerate([((4,0,3),(.08,8,6)),((0,4,3),(8,.08,6)),((0,-4,3),(8,.08,6)),((0,0,5),(8,8,.08))]):
            path=Path(output).parent/f'fixture-texture-{index}.png';texture(path,20260923+index)
            fixture_assets[path.name]=sha256(path)
            ET.SubElement(root.find('looks'),'look',name=f'm2_texture_{index}',gray='1.0',roughness='1.0',texture=str(path))
            wall=ET.SubElement(root,'static',name=f'm2_visual_wall_{index}',type='box')
            ET.SubElement(wall,'dimensions',xyz=' '.join(map(str,dimensions)))
            ET.SubElement(wall,'material',name='Neutral')
            ET.SubElement(wall,'look',name=f'm2_texture_{index}',uv_mode='0')
            ET.SubElement(wall,'world_transform',xyz=' '.join(map(str,position)),rpy='0 0 0')
    if config['case_id'] in ('calibration','imu_tilt'):
        # Known 9x7 checkerboard, 0.3 m cells, used only for projection acceptance.
        for name,gray in [('m2_board_white','0.95'),('m2_board_black','0.01')]:
            ET.SubElement(root.find('looks'),'look',name=name,gray=gray,roughness='1.0')
        for row in range(7):
            for col in range(9):
                square=ET.SubElement(root,'static',name=f'm2_board_{row}_{col}',type='box')
                ET.SubElement(square,'dimensions',xyz='0.01 0.3 0.3')
                ET.SubElement(square,'material',name='Neutral')
                ET.SubElement(square,'look',name='m2_board_white' if (row+col)%2==0 else 'm2_board_black')
                ET.SubElement(square,'world_transform',xyz=f'3.95 {-1.35+(col+.5)*.3} {1.1+(row+.5)*.3}',rpy='0 0 0')
        evidence['checkerboard']={'inner_corners':[8,6],'cell_m':.3,'plane_x_ned_m':3.945,
            'outer_top_left_yz_ned_m':[-1.35,1.1]}
    ET.indent(tree,space='  ');tree.write(output,encoding='utf-8',xml_declaration=True)
    evidence.update(scene_sha256=sha256(output),fixture_assets_sha256=fixture_assets,
        imu_rate_hz=100,imu_specific_force=True,imu_truth_orientation=False,
        camera_sampling='continuous common drawing-queue snapshot; acquisition stamp carried with PBO',
        paired_delivery_max_hz=20,scene_profile=config['scene_profile'])
    Path(output).with_suffix('.assets.json').write_text(json.dumps(evidence,indent=2)+'\n')
    return evidence


def write_stereo_calibration(profile,path):
    # IMU is colocated/aligned with base_link FLU. Optical axes: right, down, forward.
    data={}
    for i,side in enumerate(('left','right')):
        c=profile['cameras'][side];x,y,z=c['xyz_frd']
        fx,fy,cx,cy=intrinsics(c['width'],c['height'],c['horizontal_fov_deg'])
        data['cam'+str(i)]={'T_cam_imu':[[0.,-1.,0.,-y],[0.,0.,-1.,-z],[1.,0.,0.,-x],[0.,0.,0.,1.]],
            'cam_overlaps':[1-i],'camera_model':'pinhole','distortion_coeffs':[0.,0.,0.,0.],
            'distortion_model':'radtan','intrinsics':[fx,fy,cx,cy],
            'resolution':[c['width'],c['height']],'rostopic':f'sensors/stereo/{side}/image_raw',
            'timeshift_cam_imu':0.}
    # Flow arrays are accepted by OpenCV FileStorage used in pinned OpenVINS.
    class IndentedDumper(yaml.SafeDumper):
        def increase_indent(self,flow=False,indentless=False):
            return super().increase_indent(flow,False)
    Path(path).write_text('%YAML:1.0\n'+yaml.dump(data,Dumper=IndentedDumper,default_flow_style=None,sort_keys=False))
