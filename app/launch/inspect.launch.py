"""Direct Stonefish composition; upstream ArduSub entrypoint is never included."""

import signal
import json
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, EmitEvent, ExecuteProcess, OpaqueFunction, RegisterEventHandler, TimerAction
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown, matches_action
from launch.events.process import SignalProcess
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
import yaml

from uw_app.config import load_config
from uw_ui.window import close_rviz,show_window_actions
from uw_robot.description import make_urdf
from uw_simulations.scene import generate_scene


def compose(context):
    output = Path(LaunchConfiguration("run_dir").perform(context)).resolve()
    config = load_config(output / "resolved_config.yaml")
    namespace = config["namespace"]
    robot_share = Path(get_package_share_directory("uw_robot"))
    sim_share = Path(get_package_share_directory("uw_simulations"))
    upstream = Path(get_package_share_directory("stonefish_bluerov2"))
    profile_path = robot_share / "config/bluerov2_heavy.yaml"
    profile = yaml.safe_load(profile_path.read_text())
    scenario = output / "empty_water.scn"
    expected_assets = json.loads((output / "asset-lock.json").read_text())
    generate_scene(upstream, sim_share / "scenarios/empty_water.scn", profile, namespace, scenario,
                   expected_assets=expected_assets)
    (output / "robot_profile.yaml").write_bytes(profile_path.read_bytes())
    description = make_urdf(namespace, profile)
    (output / "robot.urdf").write_text(description)
    common = {"use_sim_time": True}
    simulator = Node(
        package="stonefish_ros2", executable="stonefish_simulator", name="stonefish_simulator",
        namespace=namespace, output="screen", parameters=[common],
        arguments=[str(upstream / "data"), str(scenario), "100.0", "960", "720", "medium"],
        sigterm_timeout="5", sigkill_timeout="5")
    robot = Node(package="robot_state_publisher", executable="robot_state_publisher",
                 namespace=namespace, parameters=[common, {"robot_description": description}], output="screen")
    adapter = Node(package="uw_simulations", executable="observation_adapter", namespace=namespace,
                   parameters=[common, {"frame_prefix": namespace, "robot_profile_path": str(profile_path),
                                         "observation_access": config["observation_access"]}], output="screen")
    probe = Node(package="uw_benchmark", executable="m0_probe", namespace=namespace, output="screen",
                 parameters=[common, {"frame_prefix": namespace, "run_dir": str(output),
                                       "startup_timeout_sec": float(config["startup_timeout_sec"]),
                                       "duration_sec": float(config["duration_sec"])}])
    actions = []
    gui_stopping = [False]

    def on_exit(name):
        def callback(event, context):
            with (output / "process-exits.jsonl").open("a") as stream:
                stream.write(json.dumps({"name": name, "returncode": event.returncode,
                                         "before_probe_completion": not (output / "metrics.json").exists()})+"\n")
            if context.is_shutdown:return []
            shutdown=EmitEvent(event=Shutdown(reason=f"{name} exited ({event.returncode})"))
            if gui_stopping[0]:return [shutdown] if name=="rviz" else []
            if name=="m0_probe" and config["visualization"]=="rviz":
                gui_stopping[0]=True
                def close_after_drain(context):
                    close_rviz(output)
                    return [TimerAction(period=2.,actions=[shutdown])]
                signals=[EmitEvent(event=SignalProcess(signal_number=signal.SIGINT,process_matcher=matches_action(process)))
                         for process,label in required if label!="m0_probe"]
                return signals+[TimerAction(period=1.,actions=[OpaqueFunction(function=close_after_drain)])]
            return [shutdown]
        return callback

    required = [(simulator, "stonefish_simulator"), (robot, "robot_state_publisher"),
                (adapter, "observation_adapter"), (probe, "m0_probe")]
    if config["recording_profile"] == "debug":
        topics = ["/clock", "/tf", "/tf_static", f"/{namespace}/robot_description"]
        topics += [f"/{namespace}/{name}" for name in (
            "state/odometry", "sim/ground_truth/odometry", "sensors/imu", "diagnostics",
            "sensors/stereo/left/image_raw", "sensors/stereo/right/image_raw",
            "sensors/stereo/left/camera_info", "sensors/stereo/right/camera_info")]
        qos_path = output / "bag-qos.yaml"
        qos = {t: {"reliability": "best_effort", "durability": "volatile", "history": "keep_last", "depth": 5}
               for t in topics if "/sensors/" in t or t == "/clock"}
        qos["/tf_static"] = {"reliability": "reliable", "durability": "transient_local", "history": "keep_last", "depth": 1}
        qos[f"/{namespace}/robot_description"] = dict(qos["/tf_static"])
        qos_path.write_text(yaml.safe_dump(qos))
        recorder = ExecuteProcess(cmd=["ros2", "bag", "record", "--use-sim-time", "--storage", "mcap",
                                       "--qos-profile-overrides-path", str(qos_path),
                                       "--output", str(output / "bags"), "--topics", *topics], output="screen")
        (output / "recording-topics.json").write_text(json.dumps(topics, indent=2)+"\n")
        required.insert(0, (recorder, "rosbag"))
    for process, name in required:
        actions.append(RegisterEventHandler(OnProcessExit(target_action=process, on_exit=on_exit(name))))
    actions += [p for p, name in required]
    if config["visualization"] == "rviz":
        template = Path(get_package_share_directory("uw_ui")) / "config/inspect.rviz"
        rviz = output / "inspect.rviz"
        rviz.write_text(template.read_text().replace("@NAMESPACE@", namespace))
        rviz_process=Node(package="rviz2", executable="rviz2", namespace=namespace,
                            arguments=["-d", str(rviz)], parameters=[common], output="screen",
                            additional_env={"QT_FONT_DPI": "96"})
        actions.append(RegisterEventHandler(OnProcessExit(target_action=rviz_process,on_exit=on_exit("rviz"))))
        actions = show_window_actions(output,simulator,rviz_process)+actions
        actions.append(rviz_process)
    return actions


def generate_launch_description():
    return LaunchDescription([DeclareLaunchArgument("run_dir"), OpaqueFunction(function=compose)])
