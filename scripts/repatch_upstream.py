#!/usr/bin/env python3
"""Reuse verified M0 Git objects; fetch only explicitly added locked dependencies."""
import hashlib,json,subprocess
from pathlib import Path
import yaml

old=Path('/opt/uw/m0-vendor/source-lock.yaml');new=Path('/opt/uw/vendor/source-lock.yaml')
evidence=json.loads(Path('/opt/uw/build-evidence.json').read_text())
if hashlib.sha256(old.read_bytes()).hexdigest()!=evidence['source_lock_sha256']:
    raise RuntimeError('M0 image source-lock provenance mismatch')
old_repos={r['name']:r for r in yaml.safe_load(old.read_text())['repositories']}
records=[]
for repo in yaml.safe_load(new.read_text())['repositories']:
    target=Path('/opt/uw_src')/repo['name']
    def git(*args):return subprocess.check_output(['git','-C',str(target),*args],text=True).strip()
    if repo['name'] in old_repos:
        before=old_repos[repo['name']]
        if (repo['url'],repo['commit'])!=(before['url'],before['commit']):raise RuntimeError('Rebuild cannot change an existing pinned commit')
        if git('rev-parse','HEAD')!=repo['commit']:raise RuntimeError('M0 source HEAD mismatch')
    else:
        target.mkdir(exist_ok=False)
        git('init');git('remote','add','origin',repo['url']);git('fetch','--depth','1','origin',repo['commit']);git('checkout','--detach','FETCH_HEAD')
        if git('rev-parse','HEAD')!=repo['commit']:raise RuntimeError('New pinned source HEAD mismatch')
    # These are exclusively the image's vendored checkouts, never the user's workspace.
    git('reset','--hard',repo['commit']);git('clean','-fd')
    for patch in repo['patches']:
        path=Path('/opt/uw/vendor')/patch['file']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=patch['sha256']:raise RuntimeError('Patch hash mismatch')
        git('apply','--check',str(path));git('apply',str(path))
    records.append(dict(name=repo['name'],commit=repo['commit'],patches=repo['patches'],status_after_patch=git('status','--porcelain')))
Path('/opt/uw/upstream-evidence.json').write_text(json.dumps(records,indent=2)+'\n')
