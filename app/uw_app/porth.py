"""Explicit Porth composition and evidence helpers; no control algorithms."""
import shutil
from pathlib import Path
import yaml


def prepare(out,cfg,share):
    from uw_simulations.porth_scene import load_asset,add_cave
    from uw_robot.description import make_mesh_urdf
    directory=out.parent.parent/'assets'/cfg['cave_asset']
    asset=load_asset(directory);shutil.copy2(directory/'asset.json',out/'cave-asset.json')
    add_cave(out/'m2.scn',directory,asset)
    profile=yaml.safe_load((Path(share('uw_robot'))/'config/bluerov2_heavy.yaml').read_text())
    return make_mesh_urdf(cfg['namespace'],profile,directory)
