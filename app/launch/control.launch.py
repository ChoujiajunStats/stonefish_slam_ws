"""M1 composition and process accounting; no automatic ARM in launch."""
import signal
import json,shutil
from pathlib import Path
import yaml
from ament_index_python.packages import get_package_share_directory as share
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument,EmitEvent,ExecuteProcess,OpaqueFunction,RegisterEventHandler,TimerAction
from launch.event_handlers import OnProcessExit,OnProcessStart
from launch.events import Shutdown, matches_action
from launch.events.process import SignalProcess
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from uw_app.m1_config import load_run_config
from uw_ui.window import close_rviz,show_window_actions
from uw_robot.description import make_urdf
from uw_simulations.m1_scene import generate_m1_scene


def compose(context):
    output=Path(LaunchConfiguration('run_dir').perform(context));config=load_run_config(output/'resolved_config.yaml')
    namespace=config['namespace'];profile=yaml.safe_load((Path(share('uw_robot'))/'config/bluerov2_heavy.yaml').read_text())
    for package,file,target in [('uw_robot','config/thrusters_m1.yaml','thrusters.yaml'),
                               ('uw_guard','config/defaults.yaml','guard-parameters.yaml'),
                               ('uw_controller','config/defaults.yaml','controller-parameters.yaml')]:
        shutil.copy2(Path(share(package))/file,output/target)
    upstream=Path(share('stonefish_bluerov2'));scenario=output/'empty_water.scn'
    generate_m1_scene(upstream,Path(share('uw_simulations'))/'scenarios/empty_water.scn',profile,namespace,scenario,
        json.loads((output/'asset-lock.json').read_text()),config,json.loads((output/'session.json').read_text()),output/'thrusters.yaml')
    description=make_urdf(namespace,profile);(output/'robot.urdf').write_text(description)
    (output/'robot_profile.yaml').write_text(yaml.safe_dump(profile))
    def node(package,executable,name,parameters=None,**kwargs):
        return Node(package=package,executable=executable,name=name,namespace=namespace,output='screen',
                    parameters=[{'use_sim_time':True},parameters or {}],**kwargs)
    processes=[('stonefish_simulator',node('stonefish_ros2','stonefish_simulator','stonefish_simulator',
        arguments=[str(upstream/'data'),str(scenario),'100.0','960','720','medium'])),
        ('robot_state_publisher',node('robot_state_publisher','robot_state_publisher','robot_state_publisher',{'robot_description':description})),
        ('observation_adapter',node('uw_simulations','observation_adapter','observation_adapter',{'frame_prefix':namespace,
            'robot_profile_path':str(Path(share('uw_robot'))/'config/bluerov2_heavy.yaml'),'observation_access':'PRIVILEGED_DEBUG','run_dir':str(output)})),
        ('guard',node('uw_guard','guard','control_guard',{'run_dir':str(output)})),
        ('actuator_adapter',node('uw_simulations','actuator_adapter','actuator_adapter',{'run_dir':str(output)}))]
    if config['control_mode']=='body_velocity':
        processes.append(('controller',node('uw_controller','body_velocity','body_velocity_controller',{'run_dir':str(output)})))
    processes.append(('benchmark',node('uw_benchmark','m1_case','m1_case',{'run_dir':str(output)})))
    if config['case_id'].startswith('load_'):
        processes.append(('m1_observation',node('uw_benchmark','m1_observation','m1_observation',
            {'frame_prefix':namespace,'run_dir':str(output),'startup_timeout_sec':45.0,'duration_sec':60.0})))
    if config['recording_profile']!='none':
        names=['state/odometry','control/request','control/approved','control/output','control/status',
               'control/controller_status','control/adapter_status','sim/terminal/status','sim/terminal/input',
               'sim/actuators/native_feedback','control/trajectory','diagnostics']
        if config['recording_profile']=='debug':
            names+=['sim/ground_truth/odometry','sensors/imu','robot_description']
            names += [f'sensors/stereo/{s}/{k}' for s in ('left','right') for k in ('image_raw','camera_info')]
        topics=['/clock','/tf','/tf_static']+[f'/{namespace}/{x}' for x in names]
        qos={t:{'reliability':'best_effort','durability':'volatile','history':'keep_last','depth':5} for t in topics if '/sensors/' in t or t=='/clock'}
        for t in ['/tf_static',f'/{namespace}/robot_description']:qos[t]={'reliability':'reliable','durability':'transient_local','history':'keep_last','depth':1}
        (output/'bag-qos.yaml').write_text(yaml.safe_dump(qos));(output/'recording-topics.json').write_text(json.dumps(topics,indent=2))
        (output/'recording-storage.json').write_text(json.dumps({'storage':'mcap','preset':'zstd_fast' if config['recording_profile']=='debug' else 'none','lossless':True}))
        processes.insert(0,('rosbag',ExecuteProcess(cmd=['ros2','bag','record','--use-sim-time','--storage','mcap',
          '--storage-preset-profile','zstd_fast' if config['recording_profile']=='debug' else 'none',
          '--qos-profile-overrides-path',str(output/'bag-qos.yaml'),'--output',str(output/'bags'),'--topics',*topics],output='screen')))
    if config['visualization']=='rviz':
        from uw_ui.layouts import control_layout
        p=output/'inspect.rviz'
        layout=control_layout(Path(share('uw_ui'))/'config/inspect.rviz',namespace)
        p.write_text(yaml.safe_dump(layout,sort_keys=False))
        processes.append(('rviz',node('rviz2','rviz2','rviz2',arguments=['-d',str(p)],additional_env={'QT_FONT_DPI':'96'})))
    actions=[]
    gui_stopping=[False]
    def started(name):
        def callback(event,context):
            with (output/'process-starts.jsonl').open('a') as f:
                start_ticks=int(Path(f'/proc/{event.pid}/stat').read_text().rsplit(') ',1)[1].split()[19])
                f.write(json.dumps({'name':name,'pid':event.pid,'proc_start_ticks':start_ticks})+'\n')
        return callback
    def exited(name):
        def callback(event,context):
            record={'name':name,'returncode':event.returncode,'before_case_completion':not (output/'control-metrics.json').exists()}
            with (output/'process-exits.jsonl').open('a') as f:f.write(json.dumps(record)+'\n')
            expected=json.loads((output/'expected-exits.json').read_text()) if (output/'expected-exits.json').exists() else []
            if name=='m1_observation' and (output/'observation-metrics.json').exists() and json.loads((output/'observation-metrics.json').read_text()).get('status')=='PASS':return []
            if context.is_shutdown or name in expected:return []
            shutdown=EmitEvent(event=Shutdown(reason=f'{name} exited ({event.returncode})'))
            if gui_stopping[0]:return [shutdown] if name=='rviz' else []
            if name=='rviz':return []
            if name=='benchmark' and config['visualization']=='rviz' and 'rviz' not in expected:
                gui_stopping[0]=True
                def close_after_drain(context):
                    close_rviz(output)
                    return [TimerAction(period=2.,actions=[shutdown])]
                signals=[EmitEvent(event=SignalProcess(signal_number=signal.SIGINT,process_matcher=matches_action(process)))
                         for label,process in processes if label not in ('rviz','benchmark','m1_observation')]
                return signals+[TimerAction(period=1.,actions=[OpaqueFunction(function=close_after_drain)])]
            return [shutdown]
        return callback
    for name,process in processes:
        actions += [RegisterEventHandler(OnProcessStart(target_action=process,on_start=started(name))),
                    RegisterEventHandler(OnProcessExit(target_action=process,on_exit=exited(name)))]
    if config['visualization']=='rviz':
        clients=dict(processes);actions += show_window_actions(output,clients['stonefish_simulator'],clients['rviz'])
    return actions+[p for _,p in processes]


def generate_launch_description():
    return LaunchDescription([DeclareLaunchArgument('run_dir'),OpaqueFunction(function=compose)])
