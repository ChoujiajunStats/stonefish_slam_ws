"""RViz display configuration from explicit visualization choices, without ROS."""
from pathlib import Path
import yaml


def load_layout(template, namespace):
    return yaml.safe_load(Path(template).read_text().replace('@NAMESPACE@', namespace))


def porth_layout(layout,ns):
    manager=layout['Visualization Manager'];manager['Global Options']['Fixed Frame']=ns+'/map'
    for display in manager['Displays']:
        if display.get('Class')=='rviz_default_plugins/RobotModel':display['Name']='BlueROV2 Heavy - actual asset'
    def topic(name):return {'Value':f'/{ns}/slam/{name}','Reliability Policy':'Reliable','Durability Policy':'Volatile','Depth':1}
    manager['Displays'] += [
        {'Class':'rviz_default_plugins/PointCloud2','Name':'SLAM map - stereo measurements','Enabled':True,
         'Topic':topic('cloud_map'),'Style':'Points','Size (Pixels)':3,'Color Transformer':'RGB8','Position Transformer':'XYZ','Decay Time':0},
        {'Class':'rviz_default_plugins/Path','Name':'SLAM optimized trajectory','Enabled':True,'Color':'255; 90; 130','Topic':topic('trajectory')},
        {'Class':'rviz_default_plugins/Marker','Name':'Known Porth cutaway - NOT SLAM output','Enabled':False,'Topic':topic('known_cave')}]
    manager['Views']['Current'].update({'Target Frame':ns+'/odom','Distance':7,'Pitch':.7,'Yaw':.7,'Focal Point':{'X':1.2,'Y':0.,'Z':0.}})


def estimation_layout(template, namespace, *, milestone=2, porth=False, survey=False, orb=False, orb_robot_description=None):
    if orb and (not porth or orb_robot_description is None):
        raise ValueError("ORB display requires an explicit robot description and map view")
    ns=namespace
    layout=load_layout(template, namespace)
    for display in layout['Visualization Manager']['Displays']:
        if display.get('Class')=='rviz_default_plugins/Odometry':display['Name']='OpenVINS local state'
    layout['Visualization Manager']['Displays'].append({'Class':'rviz_default_plugins/Path','Name':'OpenVINS estimated trajectory','Enabled':True,'Color':'0; 210; 180','Topic':{'Value':f'/{ns}/localization/trajectory','Reliability Policy':'Reliable','Durability Policy':'Volatile','Depth':5}})
    if milestone==3:layout['Visualization Manager']['Displays'].append({'Class':'rviz_default_plugins/Path','Name':'Mission waypoints','Enabled':True,'Color':'250; 160; 20','Topic':{'Value':f'/{ns}/navigation/path','Reliability Policy':'Reliable','Durability Policy':'Volatile','Depth':5}})
    if milestone==3:
        for display in layout['Visualization Manager']['Displays']:
            if display.get('Class')=='rviz_default_plugins/TF':display['Show Names']=False
    if milestone==3:layout['Visualization Manager']['Displays'].append({'Class':'rviz_default_plugins/Marker','Name':'Mission status','Enabled':True,'Topic':{'Value':f'/{ns}/mission/status_marker','Reliability Policy':'Reliable','Durability Policy':'Volatile','Depth':5}})
    if porth:
        porth_layout(layout,ns)
        if orb:
            for display in layout['Visualization Manager']['Displays']:
                if display.get('Name')=='SLAM map - stereo measurements':display.update({'Name':'ORB-SLAM3 sparse landmarks','Color Transformer':'FlatColor','Color':'70; 215; 255'})
                if display.get('Name')=='SLAM optimized trajectory':display['Name']='ORB-SLAM3 online keyframe trajectory'
                if display.get('Class')=='rviz_default_plugins/RobotModel':display.update({'Name':'BlueROV2 - ORB-SLAM3 pose','Description Source':'File','Description File':str(orb_robot_description)})
                if display.get('Class')=='rviz_default_plugins/Grid':display['Name']='ORB initial-body FLU grid'
                if display.get('Class') in ('rviz_default_plugins/TF','rviz_default_plugins/Odometry') or display.get('Name') in ('OpenVINS estimated trajectory','Mission waypoints','Mission status'):display['Enabled']=False
            layout['Visualization Manager']['Displays'].append({'Class':'rviz_default_plugins/Pose','Name':'ORB-SLAM3 current body pose','Enabled':True,'Shape':'Axes','Topic':{'Value':f'/{ns}/slam/pose','Reliability Policy':'Reliable','Durability Policy':'Volatile','Depth':5}})
        if survey:
            layout['Visualization Manager']['Views']['Current'].update({'Target Frame':ns+('/orb_body' if orb else '/base_link'),'Distance':12.,'Focal Point':{'X':0.,'Y':0.,'Z':0.}})
    return layout


def control_layout(template, namespace):
    layout=load_layout(template, namespace)
    layout['Visualization Manager']['Displays'] += [
        {'Class':'rviz_default_plugins/Path','Name':'Actual trajectory','Enabled':True,'Color':'0; 210; 180',
         'Topic':{'Value':f'/{namespace}/control/trajectory','Reliability Policy':'Reliable','Durability Policy':'Volatile','Depth':5}},
        {'Class':'rviz_default_plugins/Marker','Name':'Control state','Enabled':True,
         'Topic':{'Value':f'/{namespace}/control/status_marker','Reliability Policy':'Reliable','Durability Policy':'Volatile','Depth':5}}]
    return layout
