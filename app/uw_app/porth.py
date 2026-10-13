"""Explicit Porth composition and evidence helpers; no control algorithms."""
from uw_robot.profiles import load_robot, PROFILES
import shutil
from pathlib import Path
import yaml


def prepare(out,cfg,share):
    from uw_simulations.porth_scene import load_asset,add_cave
    from uw_robot.description import make_mesh_urdf
    directory=out.parent.parent/'assets'/cfg['cave_asset']
    asset=load_asset(directory);shutil.copy2(directory/'asset.json',out/'cave-asset.json')
    add_cave(out/'m2.scn',directory,asset)
    profile=load_robot(Path(share('uw_robot'))/'config',cfg['robot_profile'])
    return make_mesh_urdf(cfg['namespace'],profile,directory)
