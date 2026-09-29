"""M3 composition reuses the M2 simulator and sensor lifecycle explicitly."""
import importlib.util
from pathlib import Path
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument,OpaqueFunction


def compose(context):
    spec=importlib.util.spec_from_file_location('uw_estimate_composition',Path(__file__).with_name('estimate.launch.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.compose(context,milestone=3)


def generate_launch_description():return LaunchDescription([DeclareLaunchArgument('run_dir'),OpaqueFunction(function=compose)])
