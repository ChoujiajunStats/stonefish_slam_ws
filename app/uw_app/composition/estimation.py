"""M2 composition. Normal launch stays DISARMED; benchmark motion is explicit."""
import json,shutil,signal
from pathlib import Path
import yaml
from ament_index_python.packages import get_package_share_directory as share
from launch.actions import EmitEvent,ExecuteProcess,OpaqueFunction,RegisterEventHandler,TimerAction
from launch.event_handlers import OnProcessExit,OnProcessStart
from launch.events import Shutdown,matches_action
from launch.events.process import SignalProcess
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from uw_app.m2_config import load_config
from uw_ui.window import close_rviz,show_window_actions
from uw_robot.description import make_urdf
from uw_simulations.m2_scene import generate_m2_scene,write_stereo_calibration


def compose(context,milestone=2):
    if milestone==3:
        from uw_app.m3_config import load_config as loader
    else:loader=load_config
    out=Path(LaunchConfiguration('run_dir').perform(context));cfg=loader(out/'resolved_config.yaml');ns=cfg['namespace']
    porth=cfg['scene_profile']=='porth_sump9'
    survey=cfg.get('survey_profile')=='known_route_capture_v1'
    orb=cfg.get('slam_profile')=='orbslam3_stereo'
    profile=yaml.safe_load((Path(share('uw_robot'))/'config/bluerov2_heavy.yaml').read_text())
    for package,file,target in [('uw_robot','config/thrusters_m1.yaml','thrusters.yaml'),('uw_guard','config/defaults.yaml','guard-parameters.yaml'),('uw_controller','config/defaults.yaml','controller-parameters.yaml')]:
        shutil.copy2(Path(share(package))/file,out/target)
    for name in ('openvins.yaml','imu.yaml'):shutil.copy2(Path(share('uw_localization'))/'config'/name,out/name)
    write_stereo_calibration(profile,out/'stereo.yaml')
    upstream=Path(share('stonefish_bluerov2'));scene=out/'m2.scn'
    generate_m2_scene(upstream,Path(share('uw_simulations'))/'scenarios/empty_water.scn',profile,ns,scene,json.loads((out/'asset-lock.json').read_text()),cfg,json.loads((out/'session.json').read_text()),out/'thrusters.yaml')
    urdf=make_urdf(ns,profile)
    if porth:
        from uw_app.porth import prepare
        urdf=prepare(out,cfg,share)
        if survey:
            from uw_app.survey import prepare as prepare_survey
            prepare_survey(out,cfg)
    if orb:
        from uw_robot.description import isolated_visual_urdf
        (out/'orb-robot.urdf').write_text(isolated_visual_urdf(urdf,ns+'/orb_body'))
    (out/'robot.urdf').write_text(urdf);(out/'robot_profile.yaml').write_text(yaml.safe_dump(profile))
    def node(package,executable,name,params=None,**kw):
        return Node(package=package,executable=executable,name=name,namespace=ns,output='screen',parameters=[{'use_sim_time':True},params or {}],**kw)
    truth_state=[('state/odometry','sim/ground_truth/odometry')] if milestone==2 or survey else []
    state_prefix=ns+'/truth' if milestone==2 or survey else ns
    if milestone==3:
        for package in ('navigation','tasks'):shutil.copy2(Path(share('uw_'+package))/'config/defaults.yaml',out/(package+'-parameters.yaml'))
    if porth:
        path=out/'tasks-parameters.yaml';parameters=yaml.safe_load(path.read_text())
        parameters.update(horizontal_goal_abs_m=3.,maximum_timeout_sec=130.)
        path.write_text(yaml.safe_dump(parameters))
    processes=[('stonefish_simulator',node('stonefish_ros2','stonefish_simulator','stonefish_simulator',arguments=[str(upstream/'data'),str(scene),'100.0','960','720','medium'])),
        ('robot_state_publisher',node('robot_state_publisher','robot_state_publisher','robot_state_publisher',{'robot_description':urdf})),
        ('debug_truth',node('uw_simulations','m2_debug_truth','m2_debug_truth',{'frame_prefix':ns})),
        ('perception',node('uw_perception','sensors','m2_sensors',{'run_dir':str(out)})),
        ('localization',node('uw_localization','openvins','openvins',{'frame_prefix':ns,'run_id':out.name,'config_path':str(out/'openvins.yaml'),'allow_static_initialization':milestone==3,'normalize_health_image':survey})),
        ('guard',node('uw_guard','guard','control_guard',{'run_dir':str(out),'state_frame_prefix':state_prefix,**({'estimated_horizontal_limit_m':4.,'estimated_vertical_limit_m':1.} if porth else {})},remappings=truth_state)),
        ('controller',node('uw_controller','body_velocity','body_velocity_controller',{'run_dir':str(out),'state_frame_prefix':state_prefix},remappings=truth_state)),
        ('actuator_adapter',node('uw_simulations','actuator_adapter','actuator_adapter',{'run_dir':str(out)})),
        ('benchmark',node('uw_benchmark','survey_case' if survey else 'porth_case' if porth else 'm3_case' if milestone==3 else 'm2_case','m3_case' if milestone==3 else 'm2_case',{'run_dir':str(out)}))]
    if orb:
        from uw_localization.orbslam3 import prepare as prepare_orb
        processes.append(('slam',node('uw_localization','orbslam3','orbslam3',prepare_orb(out,ns,profile,Path(share('uw_localization'))/'config/orbslam3_stereo.yaml'),sigterm_timeout='120',sigkill_timeout='10')))
    elif porth:
        from uw_localization.rtabmap import prepare as slam_parameters
        remaps=[('odom','state/odometry'),('info','slam/info'),('mapGraph','slam/map_graph'),('mapData','slam/map_data'),('cloud_map','slam/cloud_map')]
        remaps += [(f'{s}/image_rect',f'sensors/stereo/{s}/image_raw') for s in ('left','right')]
        remaps += [(f'{s}/camera_info',f'sensors/stereo/{s}/camera_info') for s in ('left','right')]
        processes.append(('slam',node('rtabmap_slam','rtabmap','rtabmap',slam_parameters(out,ns,Path(share('uw_localization'))/'config/rtabmap_stereo.yaml',long_survey=survey),remappings=remaps)))
    if milestone==3 and not survey:
        processes += [('navigation',node('uw_navigation','tracker','navigation',{'run_dir':str(out)})),('tasks',node('uw_tasks','missions','missions',{'run_dir':str(out)}))]
    if cfg['recording_profile']!='none':
        names=['state/odometry','sim/ground_truth/odometry','sensors/imu','perception/status','localization/status','control/request','control/status','control/controller_status','sim/terminal/status','sim/actuators/native_feedback','localization/trajectory']
        if milestone==3:names += ['navigation/goal','navigation/status','navigation/path','mission/status','control/approved','control/output','control/adapter_status']
        if orb:names += ['slam/status','slam/pose','slam/trajectory','slam/cloud_map']
        elif porth:names += ['slam/info','slam/map_graph','slam/trajectory']
        if cfg['recording_profile'] in ('sensors','debug'):
            names += [f'sensors/stereo/{s}/{k}' for s in ('left','right') for k in ('image_raw','camera_info')]
        topics=['/clock','/tf','/tf_static']+[f'/{ns}/{s}' for s in names]
        qos={t:{'reliability':'best_effort','durability':'volatile','history':'keep_last','depth':10} for t in topics}
        qos['/tf_static']={'reliability':'reliable','durability':'transient_local','history':'keep_last','depth':1}
        (out/'bag-qos.yaml').write_text(yaml.safe_dump(qos));(out/'recording-topics.json').write_text(json.dumps(topics,indent=2))
        processes.insert(0,('rosbag',ExecuteProcess(cmd=['ros2','bag','record','--use-sim-time','--storage','mcap','--storage-preset-profile','zstd_fast','--qos-profile-overrides-path',str(out/'bag-qos.yaml'),'--output',str(out/'bags'),'--topics',*topics],output='screen')))
    if cfg['visualization']=='rviz':
        from uw_ui.layouts import estimation_layout
        rviz=out/'inspect.rviz'
        layout=estimation_layout(Path(share('uw_ui'))/'config/inspect.rviz', ns, milestone=milestone, porth=porth, survey=survey, orb=orb, orb_robot_description=out/'orb-robot.urdf')
        rviz.write_text(yaml.safe_dump(layout,sort_keys=False));processes.append(('rviz',node('rviz2','rviz2','rviz2',arguments=['-d',str(rviz)],additional_env={'QT_FONT_DPI':'96'})))
    actions=[];stopping=[False];finished=set()
    def started(name):
        def cb(event,context):
            start_ticks=int(Path(f'/proc/{event.pid}/stat').read_text().rsplit(') ',1)[1].split()[19])
            with (out/'process-starts.jsonl').open('a') as f:f.write(json.dumps(dict(name=name,pid=event.pid,proc_start_ticks=start_ticks))+'\n')
        return cb
    def exited(name):
        def cb(event,context):
            finished.add(name)
            with (out/'process-exits.jsonl').open('a') as f:f.write(json.dumps(dict(name=name,returncode=event.returncode,before_case_completion=not (out/f'm{milestone}-metrics.json').exists()))+'\n')
            expected=json.loads((out/'expected-exits.json').read_text()) if (out/'expected-exits.json').exists() else []
            if context.is_shutdown or name in expected:return []
            shutdown=EmitEvent(event=Shutdown(reason=f'{name} exited ({event.returncode})'))
            if stopping[0]:
                if porth:return [shutdown] if finished=={label for label,_ in processes} else []
                return [shutdown] if name=='rviz' else []
            if name=='rviz':return []
            if name=='benchmark' and cfg['visualization']=='rviz' and 'rviz' not in expected:
                stopping[0]=True
                def close(context):close_rviz(out);return [TimerAction(period=15. if porth else 2.,actions=[shutdown])]
                return [EmitEvent(event=SignalProcess(signal_number=signal.SIGINT,process_matcher=matches_action(p))) for label,p in processes if label not in ('rviz','benchmark')]+[TimerAction(period=1.,actions=[OpaqueFunction(function=close)])]
            return [shutdown]
        return cb
    for name,process in processes:actions.extend([RegisterEventHandler(OnProcessStart(target_action=process,on_start=started(name))),RegisterEventHandler(OnProcessExit(target_action=process,on_exit=exited(name)))])
    if cfg['visualization']=='rviz':
        clients=dict(processes);actions += show_window_actions(out,clients['stonefish_simulator'],clients['rviz'])
    return actions+[p for _,p in processes]

