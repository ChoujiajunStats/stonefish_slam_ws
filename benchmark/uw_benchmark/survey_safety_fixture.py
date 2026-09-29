"""Explicit SIGKILL regression in one identified survey run, with native evidence."""
import argparse,json,os,subprocess,time
from pathlib import Path


def inject(data,run_id,repo):
    data=Path(data);repo=Path(repo).resolve()
    if Path(run_id).name!=run_id:raise ValueError('Expected exact run directory name')
    run=data/'runs'/run_id;session=json.loads((data/'active-session.json').read_text())
    if Path(session['run_dir']).name!=run_id or not session['container'].startswith('uw-run-'):raise ValueError('Run is not active')
    info=json.loads(subprocess.check_output(['docker','inspect',session['container']],text=True))[0]
    if not info['State']['Running'] or not any(m['Source']==str(repo) and m['Destination']=='/workspace' for m in info['Mounts']):raise ValueError('Wrong container workspace')
    cfg=json.loads((run/'manifest.json').read_text())
    if cfg.get('milestone')!='PORTH_SURVEY':raise ValueError('Only explicit simulation survey runs are eligible')
    if (run/'safety-injection.json').exists():raise ValueError('Never overwrite injection evidence')
    started=time.monotonic()
    while time.monotonic()-started<60:
        p=json.loads((run/'survey-progress.json').read_text()) if (run/'survey-progress.json').exists() else {}
        if p.get('progress_m',0)>2:break
        if json.loads((run/'manifest.json').read_text())['status']!='RUNNING':raise RuntimeError('Run ended before injection')
        time.sleep(.2)
    else:raise RuntimeError('No moving collection in 60 seconds')
    processes=[json.loads(s) for s in (run/'process-starts.jsonl').read_text().splitlines()]
    target=next(x for x in processes if x['name']=='actuator_adapter')
    (run/'expected-exits.json').write_text(json.dumps(['actuator_adapter'])+'\n')
    code="""import json,os,signal,sys,time
from pathlib import Path
pid=int(sys.argv[1]);ticks=int(sys.argv[2]);out=Path(sys.argv[3])
actual=int(Path(f'/proc/{pid}/stat').read_text().rsplit(') ',1)[1].split()[19])
assert actual==ticks and b'actuator_adapter' in Path(f'/proc/{pid}/cmdline').read_bytes()
before=time.monotonic_ns();os.kill(pid,signal.SIGKILL);after=time.monotonic_ns()
out.write_text(json.dumps(dict(operation='SIGKILL',process='actuator_adapter',pid=pid,proc_start_ticks=ticks,injection_before_ns=before,injection_after_ns=after,threshold_sec=.50),indent=2)+'\\n')
"""
    subprocess.run(['docker','exec','--user',f'{os.getuid()}:{os.getgid()}',session['container'],'python3','-c',code,
        str(target['pid']),str(target['proc_start_ticks']),session['run_dir']+'/safety-injection.json'],check=True)
    while time.monotonic()-started<90:
        if json.loads((run/'manifest.json').read_text())['status']!='RUNNING':break
        time.sleep(.5)
    event=json.loads((run/'safety-injection.json').read_text());t=event['injection_before_ns']
    rows=[json.loads(s) for s in (run/'m3-samples.jsonl').read_text().splitlines()]
    terminal=[p for p in rows if p['kind']=='terminal'];before=[p for p in terminal if int(p['wall_ns'])<t]
    after=[p for p in terminal if int(p['wall_ns'])>=t]
    neutral=next((p for p in after if p['state']=='FAULT' and all(abs(float(x))<1e-9 for x in p['receiver_setpoint'])),None)
    latency=(int(neutral['neutral_ns'])-t)*1e-9 if neutral else None
    exits=[json.loads(s) for s in (run/'process-exits.jsonl').read_text().splitlines()]
    checks=dict(moving_output_before_kill=bool(before) and max(abs(float(x)) for x in before[-1]['receiver_setpoint'])>.01,
        killed_exact_adapter=any(p['name']=='actuator_adapter' and p['returncode']==-9 for p in exits),
        receiver_neutral_within_budget=latency is not None and 0<=latency<=.50,
        physics_continued=bool(after) and int(after[-1]['physics_ns'])>t+500000000,
        latched_fault=bool(neutral) and all(p['state']=='FAULT' for p in after if int(p['wall_ns'])>=int(neutral['wall_ns'])),
        exactly_eight_channels=all(len(p['names'])==8 for p in terminal))
    result=dict(run_id=run_id,status='PASS' if all(checks.values()) else 'FAIL',checks=checks,
        native_receiver_neutral_latency_sec=latency,injection=event,collection_status=json.loads((run/'m3-metrics.json').read_text())['status'],
        process_exit_codes=exits,terminal_timeline=[dict(seconds=(int(p['wall_ns'])-t)*1e-9,state=p['state'],reason=p['reason'],
            receiver=list(map(float,p['receiver_setpoint'])),rpm=list(map(float,p['rpm'])),thrust_N=list(map(float,p['thrust_N']))) for p in terminal if -.5<(int(p['wall_ns'])-t)*1e-9<3])
    (run/'safety-fixture-result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('terminal_timeline','process_exit_codes')},indent=2))
    return 0 if all(checks.values()) else 1


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run_id');p.add_argument('--data-root',required=True);p.add_argument('--repo',required=True)
    a=p.parse_args();raise SystemExit(inject(a.data_root,a.run_id,a.repo))


if __name__=='__main__':main()
