"""Sequential M3 host orchestration; ROS and analysis dependencies stay in containers."""
import argparse,json,os,shutil,subprocess,uuid
from pathlib import Path
import yaml
from uw_benchmark.campaign import verify_freeze


def main(args=None):
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['diagnostic','tuning','formal'],default='formal');p.add_argument('--cases',nargs='+',required=True);p.add_argument('--continue-on-failure',action='store_true');a=p.parse_args(args)
    repo=Path(__file__).resolve().parents[2];data=Path(os.environ.get('UW_DATA_ROOT',str(Path.home()/'.local/share/stonefish-slam')))
    spec=yaml.safe_load((repo/'test/m3-acceptance.yaml').read_text());base=yaml.safe_load((repo/'config/run.m3.yaml').read_text())
    entries={**spec['cases'],**spec.get('regressions',{})};names=[]
    for name in a.cases:names.extend([k for k,v in entries.items() if v['group']==name] or [name])
    if len(set(names))!=len(names):raise ValueError('Duplicate case selection')
    for name in names:
        if name not in entries:raise ValueError('Unknown case '+name)
    batch='m3-'+a.phase+'-'+uuid.uuid4().hex[:10];folder=repo/'config/generated'/batch;folder.mkdir(parents=True,exist_ok=False)
    reports=data/'reports';reports.mkdir(exist_ok=True);results=[]
    for name in names:
        if a.phase=='formal':
            freeze=json.loads((repo/'test/m3-freeze.json').read_text());image=subprocess.check_output(['docker','image','inspect',os.environ.get('UW_IMAGE','stonefish-slam:orbslam3'),'--format','{{.Id}}'],text=True).strip();verify_freeze(repo,freeze,image)
        case=entries[name];milestone=case.get('milestone',3)
        entry='m3' if milestone==3 else 'm2' if milestone==2 else 'run'
        config_name={0:'run.empty_water.example.yaml',1:'run.m1.yaml',2:'run.m2.yaml',3:'run.m3.yaml'}[milestone]
        cfg=yaml.safe_load((repo/'config'/config_name).read_text())
        if milestone>0:
            cfg.update(run_id='m3_'+a.phase+'_'+name,case_id=case.get('case_id',name),evaluation_phase=a.phase if milestone==3 else 'diagnostic',visualization='none',recording_profile='control' if milestone==1 else 'state')
        cfg.update({k:v for k,v in case.items() if k in cfg})
        path=folder/(name+'.yaml');path.write_text(yaml.safe_dump(cfg,sort_keys=False));log=reports/(batch+'-'+name+'.log')
        active=data/'active-session.json';prior=json.loads(active.read_text())['run_dir'] if active.exists() else None
        with log.open('w') as stream:r=subprocess.run([str(repo/'scripts/uw'),entry,str(path)],cwd=repo,stdout=stream,stderr=subprocess.STDOUT,env=dict(os.environ,UW_IMAGE=os.environ.get('UW_IMAGE','stonefish-slam:orbslam3')))
        current=json.loads(active.read_text()) if active.exists() else {}
        if current.get('run_dir')==prior:result=dict(case=name,status='NOT_RUN',returncode=r.returncode,run_dir=None,log=str(log))
        else:
            out=data/'runs'/Path(current['run_dir']).name;m=json.loads((out/'manifest.json').read_text())
            if a.phase=='formal':shutil.copy2(repo/'test/m3-freeze.json',out/'campaign-freeze.json')
            result=dict(case=name,status=m.get('test_verdict','PASS' if m['status']=='SUCCEEDED' else 'FAIL'),process_status=m['status'],returncode=r.returncode,run_dir=str(out),log=str(log))
        results.append(result);(reports/(batch+'.json')).write_text(json.dumps(dict(batch=batch,phase=a.phase,results=results),indent=2)+'\n');print(json.dumps(result),flush=True)
        if r.returncode and not a.continue_on_failure:break
    return 0 if len(results)==len(names) and all(x['status']=='PASS' for x in results) else 1


if __name__=='__main__':raise SystemExit(main())
