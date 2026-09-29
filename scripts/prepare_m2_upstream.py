#!/usr/bin/env python3
"""Apply additive M2 patches only to the locked, already-patched M1 image sources."""
import hashlib
import json
from pathlib import Path
import subprocess
import yaml

root = Path('/opt/uw/m2-vendor')
lock = yaml.safe_load((root/'source-lock.m2.yaml').read_text())
parent = Path('/opt/uw/vendor/source-lock.yaml')
assert hashlib.sha256(parent.read_bytes()).hexdigest() == lock['parent_source_lock_sha256']
parent_lock = yaml.safe_load(parent.read_text())
for patch in lock['additive_patches']:
    target = Path('/opt/uw_src')/patch['repository']
    filename = root/patch['path']
    assert hashlib.sha256(filename.read_bytes()).hexdigest() == patch['sha256']
    subprocess.run(['git','-C',str(target),'apply','--check',str(filename)],check=True)
    subprocess.run(['git','-C',str(target),'apply',str(filename)],check=True)
repo = lock['open_vins']
target = Path('/opt/uw_src/open_vins')
assert subprocess.check_output(['git','-C',str(target),'rev-parse','HEAD'],text=True).strip() == repo['commit']
for patch in repo.get('patches',[]):
    filename = root/patch['path']
    assert hashlib.sha256(filename.read_bytes()).hexdigest() == patch['sha256']
    subprocess.run(['git','-C',str(target),'apply',str(filename)],check=True)
(Path('/opt/uw')/'m2-upstream-evidence.json').write_text(json.dumps(lock,indent=2)+'\n')

assert subprocess.check_output(['git','-C','/opt/uw_src/ceres','rev-parse','HEAD'],text=True).strip() == lock['ceres']['commit']
