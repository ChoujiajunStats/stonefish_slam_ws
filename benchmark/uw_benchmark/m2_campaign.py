"""Sequential M2 host orchestration; ROS and analysis dependencies stay in containers."""
import argparse,json,os,subprocess,uuid
from pathlib import Path
import yaml
from uw_benchmark.campaign import verify_freeze


def main(args=None):
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['diagnostic','tuning','formal'],default='formal');p.add_argument('--cases',nargs='+',required=True);p.add_argument('--continue-on-failure',action='store_true');a=p.parse_args(args)
    repo=Path(__file__).resolve().parents[2];data=Path(os.environ.get('UW_DATA_ROOT',str(Path.home()/'.local/share/stonefish-slam')))
    spec=yaml.safe_load((repo/'test/m2-acceptance.yaml').read_text());base=yaml.safe_load((repo/'config/run.m2.yaml').read_text())
    names=[]
    for name in a.cases:names.extend([k for k,v in spec['cases'].items() if v['group']==name] or [name])
    if len(set(names))!=len(names):raise ValueError('Duplicate case selection')
    for name in names:
        if name not in spec['cases']:raise ValueError('Unknown case '+name)
    batch='m2-'+a.phase+'-'+uuid.uuid4().hex[:10];folder=repo/'config/generated'/batch;folder.mkdir(parents=True,exist_ok=False)
    reports=data/'reports';reports.mkdir(exist_ok=True);results=[]
    for name in names:
        if a.phase=='formal':
            freeze=json.loads((repo/'test/m2-freeze.json').read_text());image=subprocess.check_output(['docker','image','inspect',os.environ.get('UW_IMAGE','stonefish-slam:orbslam3'),'--format','{{.Id}}'],text=True).strip();verify_freeze(repo,freeze,image)
        cfg=dict(base);case=spec['cases'][name]
        cfg.update(run_id='m2_'+a.phase+'_'+name,case_id=name,evaluation_phase=a.phase,visualization='none',recording_profile='state')
        cfg.update({k:v for k,v in case.items() if k in cfg})
        path=folder/(name+'.yaml');path.write_text(yaml.safe_dump(cfg,sort_keys=False));log=reports/(batch+'-'+name+'.log')
        active=data/'active-session.json';prior=json.loads(active.read_text())['run_dir'] if active.exists() else None
        with log.open('w') as stream:r=subprocess.run([str(repo/'scripts/uw'),'m2',str(path)],cwd=repo,stdout=stream,stderr=subprocess.STDOUT)
        current=json.loads(active.read_text()) if active.exists() else {}
        if current.get('run_dir')==prior:result=dict(case=name,status='NOT_RUN',returncode=r.returncode,run_dir=None,log=str(log))
        else:
            out=data/'runs'/Path(current['run_dir']).name;m=json.loads((out/'manifest.json').read_text())
            result=dict(case=name,status=m['test_verdict'],process_status=m['status'],returncode=r.returncode,run_dir=str(out),log=str(log))
        results.append(result);(reports/(batch+'.json')).write_text(json.dumps(dict(batch=batch,phase=a.phase,results=results),indent=2)+'\n');print(json.dumps(result),flush=True)
        if r.returncode and not a.continue_on_failure:break
    return 0 if len(results)==len(names) and all(x['status']=='PASS' for x in results) else 1


if __name__=='__main__':raise SystemExit(main())
