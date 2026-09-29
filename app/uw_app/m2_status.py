"""Read-only status from run evidence; stale files never imply live tracking."""
import json,sys,time
from pathlib import Path


def main():
    root=Path(sys.argv[1]);active=json.loads((root/'active-session.json').read_text())
    if not active.get('m2'):raise SystemExit('The last active session is not M2')
    folder=root/'runs'/Path(active['run_dir']).name
    manifest=json.loads((folder/'manifest.json').read_text())
    path=folder/'localization-health.json';health=json.loads(path.read_text()) if path.exists() else {}
    age=time.monotonic()-health.get('wall',0)
    print(json.dumps(dict(run_dir=str(folder),process_status=manifest['status'],test_verdict=manifest['test_verdict'],
        current_health=health.get('state','NOT_READY') if manifest['status']=='RUNNING' and age<.5 else 'STALE_OR_STOPPED',
        last_received_health=health,wall_age_sec=age if health else None),indent=2))


if __name__=='__main__':main()
