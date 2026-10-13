"""Resolve robot-specific acceptance protocols without duplicating baseline cases."""
from pathlib import Path
import yaml
from uw_robot.profiles import require_profile


def control_protocol(repo, robot_profile):
    require_profile(robot_profile)
    root=Path(repo)/'test'
    specification=yaml.safe_load((root/'m1-acceptance.yaml').read_text())
    if robot_profile=='bluerov2_six_disaware':
        variant=yaml.safe_load((root/'six-thruster-acceptance.yaml').read_text())
        if variant.pop('extends')!='m1-acceptance.yaml':raise ValueError('Invalid acceptance parent')
        for name in variant.pop('excluded_cases'):
            del specification['cases'][name]
        specification.update(variant)
    return specification
