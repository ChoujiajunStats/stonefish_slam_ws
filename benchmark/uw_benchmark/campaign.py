"""Host-side sequential case orchestration; all ROS execution stays in containers."""
import argparse,hashlib,json,os
from pathlib import Path
import subprocess,time,uuid
import yaml


def verify_freeze(repo, freeze, image_id):
    """Check again before every case: a batch cannot silently span runtime edits."""
    if image_id != freeze['image_id']:
        raise RuntimeError('Formal image differs from freeze')
    for file, digest in freeze['files'].items():
        if hashlib.sha256((repo / file).read_bytes()).hexdigest() != digest:
            raise RuntimeError('Formal freeze differs: ' + file)


def main(args=None):
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['diagnostic','tuning','formal'],default='formal')
    p.add_argument('--cases',nargs='+',required=True);p.add_argument('--continue-on-failure',action='store_true')
    p.add_argument('--probe-faults',action='store_true');options=p.parse_args(args)
    repo=Path(__file__).resolve().parents[2];data=Path(os.environ.get('UW_DATA_ROOT',str(Path.home()/'.local/share/stonefish-slam')))
    specification=yaml.safe_load((repo/'test/m1-acceptance.yaml').read_text());names=[]
    for name in options.cases:
        matches=[k for k,v in specification['cases'].items() if v['group']==name]
        names+=matches or [name]
    if options.phase=='formal':
        freeze=json.loads((repo/'test/m1-freeze.json').read_text())
        image_id=subprocess.check_output(['docker','image','inspect',os.environ.get('UW_IMAGE','stonefish-slam:orbslam3'),'--format','{{.Id}}'],text=True).strip()
        verify_freeze(repo, freeze, image_id)
    batch=f'm1-{options.phase}-{uuid.uuid4().hex[:10]}';reports=data/'reports';reports.mkdir(exist_ok=True)
    folder=repo/'config/generated'/batch;folder.mkdir(parents=True,exist_ok=False)
    base=yaml.safe_load((repo/'config/run.m1.yaml').read_text());results=[]
    for name in names:
        if options.phase == 'formal':
            image_id = subprocess.check_output(['docker','image','inspect',os.environ.get('UW_IMAGE','stonefish-slam:orbslam3'),'--format','{{.Id}}'],text=True).strip()
            verify_freeze(repo, freeze, image_id)
        if name=='m0':config=yaml.safe_load((repo/'config/run.empty_water.example.yaml').read_text())
        else:
            spec=specification['cases'][name];config=dict(base)
            config.update(run_id=f'{options.phase}_{name}',case_id=name,evaluation_phase=options.phase,
                control_mode='actuator_probe' if name.startswith('probe_') or name=='authority_validation' or options.probe_faults else 'body_velocity',
                fixed_fixture=name.startswith('probe_') or name=='authority_validation' or options.probe_faults,visualization='none',recording_profile='control',
                initial_rpy_enu_deg=spec.get('initial_rpy_enu_deg',[0.,0.,90.]),duration_sec=90. if name.startswith('load_') else 50.)
            if name.startswith('load_'):config.update(visualization='rviz',recording_profile='debug')
            if name=='fault_rviz':config['visualization']='rviz'
        path=folder/f'{name}-{len(results)+1}.yaml';path.write_text(yaml.safe_dump(config,sort_keys=False))
        log=reports/f'{batch}-{name}-{len(results)+1}.log'
        active_path=data/'active-session.json'
        previous=json.loads(active_path.read_text()).get('run_dir') if active_path.exists() else None
        with log.open('w') as stream:r=subprocess.run([str(repo/'scripts/uw'),'run',str(path)],cwd=repo,stdout=stream,stderr=subprocess.STDOUT)
        active=json.loads(active_path.read_text()) if active_path.exists() else {}
        if active.get('run_dir')==previous:
            result=dict(case=name,returncode=r.returncode,run_id=None,run_dir=None,status='NOT_RUN',process_status='NOT_STARTED',log=str(log))
        else:
            run=data/'runs'/Path(active['run_dir']).name
            manifest=json.loads((run/'manifest.json').read_text())
            result=dict(case=name,returncode=r.returncode,run_id=run.name,run_dir=str(run),
                status=manifest.get('test_verdict',manifest['status']),process_status=manifest['status'],log=str(log))
        results.append(result);(reports/f'{batch}.json').write_text(json.dumps(dict(batch=batch,phase=options.phase,results=results),indent=2)+'\n')
        print(json.dumps(result),flush=True)
        if r.returncode and not options.continue_on_failure:break
    print('Campaign evidence:',reports/f'{batch}.json',flush=True)
    return 0 if len(results)==len(names) and all(r['returncode']==0 for r in results) else 1


if __name__=='__main__':raise SystemExit(main())
