"""M2 launch entrypoint; composition is installed with uw_app."""
from functools import partial
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from uw_app.composition.estimation import compose


def generate_launch_description():
    return LaunchDescription([DeclareLaunchArgument('run_dir'),
                              OpaqueFunction(function=partial(compose, milestone=2))])
