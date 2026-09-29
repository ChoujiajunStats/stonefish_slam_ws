"""Evidence-backed status with explicit freshness, including after container exit."""
import json,sys,time
from pathlib import Path


def main():
    root=Path(sys.argv[1]);active=json.loads((root/'active-session.json').read_text())
    if not active.get('m3'):raise SystemExit('The last active session is not M3')
    out=root/'runs'/Path(active['run_dir']).name;manifest=json.loads((out/'manifest.json').read_text())
    def read(name):return json.loads((out/name).read_text()) if (out/name).exists() else {}
    health=read('localization-health.json');mission=read('mission-status.json');guard=read('control-status.json');running=manifest['status']=='RUNNING';now=time.monotonic()
    if '--control' in sys.argv:
        if not running or now-guard.get('wall_ns',0)*1e-9>=.5:raise SystemExit('Control status is stale or simulation stopped')
        print(json.dumps(guard,indent=2));return
    print(json.dumps(dict(run_dir=str(out),process_status=manifest['status'],test_verdict=manifest['test_verdict'],
        scope=manifest.get('milestone'),control_state_source=manifest.get('diagnostic_controller_state') or manifest.get('state_source'),
        survey_progress=read('survey-progress.json') if manifest.get('milestone')=='PORTH_SURVEY' else None,
        current_estimator=health.get('state','NOT_READY') if running and now-health.get('wall',0)<.5 else 'STALE_OR_STOPPED',
        current_mission=mission.get('state','NOT_READY') if running and now-mission.get('wall_ns',0)*1e-9<.5 else 'STALE_OR_STOPPED',
        current_control=guard.get('state','NOT_READY') if running and now-guard.get('wall_ns',0)*1e-9<.5 else 'STALE_OR_STOPPED',last_control=guard,last_mission=mission,last_estimator=health),indent=2))


if __name__=='__main__':main()
