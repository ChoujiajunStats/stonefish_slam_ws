"""Workspace command dispatch; algorithms and ROS nodes live in their own packages."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid
from .paths import REPO, PACKAGES
from .environment import compose_env, compose, require_docker, prepare_xauth, doctor

def source_env():
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env["PYTHONPATH"] = os.pathsep.join(str(REPO / p) for p in PACKAGES)
    return env



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor")
    commands.add_parser("compose-config")
    commands.add_parser("build")
    test = commands.add_parser("test")
    test.add_argument("--local", action="store_true", help="Use existing host Python only; install nothing")
    validate = commands.add_parser("validate")
    validate.add_argument("config", nargs="?", default="config/run.empty_water.example.yaml")
    validate.add_argument("--local", action="store_true")
    run = commands.add_parser("run")
    run.add_argument("config", nargs="?", default="config/run.empty_water.example.yaml")
    m1 = commands.add_parser('m1')
    m1.add_argument('config',nargs='?',default='config/run.m1.yaml')
    m2 = commands.add_parser('m2')
    m2.add_argument('config',nargs='?',default='config/run.m2.yaml')
    m3=commands.add_parser('m3');m3.add_argument('config',nargs='?',default='config/run.m3.yaml')
    coverage=commands.add_parser('survey-coverage');coverage.add_argument('run_id');coverage.add_argument('export_dir')
    porth=commands.add_parser('porth');porth.add_argument('config',nargs='?',default='config/run.porth.yaml');porth.add_argument('--arm',action='store_true',help='Explicitly authorize the finite prescribed data-collection path')
    porth.add_argument('--water-jerlov',type=float,help='Survey only: native optical water parameter [0,1], recorded in the new run')
    export=commands.add_parser('slam-export');export.add_argument('run_id')
    commands.add_parser('m3-status')
    for action in ('mission','mission-cancel'):
        sub=commands.add_parser(action);sub.add_argument('--arm',action='store_true');sub.add_argument('--waypoint',nargs=4,type=float,action='append');sub.add_argument('--timeout',type=float,default=60.)
    m3_accept=commands.add_parser('m3-acceptance')
    m3_accept.add_argument('--phase',choices=['diagnostic','tuning','formal'],default='formal');m3_accept.add_argument('--cases',nargs='+',required=True);m3_accept.add_argument('--continue-on-failure',action='store_true')
    for action in ('status','arm','disarm','clear-fault','command'):
        sub=commands.add_parser(action)
        sub.add_argument('--velocity',nargs=4,type=float,default=[0.,0.,0.,0.])
        sub.add_argument('--seconds',type=float,default=1.)
    accept=commands.add_parser('acceptance')
    accept.add_argument('--phase',choices=['diagnostic','tuning','formal'],default='formal')
    accept.add_argument('--cases',nargs='+',required=True)
    accept.add_argument('--continue-on-failure',action='store_true')
    accept.add_argument('--probe-faults',action='store_true')
    commands.add_parser('m2-status')
    m2_accept=commands.add_parser('m2-acceptance')
    m2_accept.add_argument('--phase',choices=['diagnostic','tuning','formal'],default='formal')
    m2_accept.add_argument('--cases',nargs='+',required=True)
    m2_accept.add_argument('--continue-on-failure',action='store_true')
    assets = commands.add_parser("assets", help="Verify/import/export the external Porth bundle")
    assets.add_argument("action", choices=("verify", "import", "export"))
    assets.add_argument("--source-data-root", type=Path)
    assets.add_argument("--bundle", type=Path)
    for command_parser in commands.choices.values():
        command_parser.add_argument("--profile", choices=tuple(json.loads((REPO / "docker/profiles.json").read_text())),
                                    default=os.environ.get("UW_PROFILE", "orbslam3"))
    options = parser.parse_args()
    os.environ["UW_PROFILE"] = options.profile
    os.chdir(REPO)
    resolved_env, _ = compose_env()
    os.environ.update({k: resolved_env[k] for k in ("UW_DATA_ROOT", "UW_IMAGE")})
    formal_files = {"acceptance": "m1-freeze.json", "m2-acceptance": "m2-freeze.json", "m3-acceptance": "m3-freeze.json"}
    if options.command in formal_files and options.phase == "formal":
        if not (REPO / "test" / formal_files[options.command]).is_file():
            raise RuntimeError("Historical freezes are archived in docs/history/freezes. "
                               "Freeze this workspace and image before formal evaluation; see docs/deployment.md.")
    if options.command == "assets":
        from .assets import run
        env, _ = compose_env()
        return run(options, Path(env["UW_DATA_ROOT"]))
    if options.command=='survey-coverage':
        env,project=compose_env();require_docker()
        return compose(['run','--rm','--no-deps','-e','PYTHONPATH=/workspace/runtime:/workspace/app:/workspace/benchmark:/workspace/simulations','tools','python3','-m','uw_benchmark.survey_coverage',options.run_id,options.export_dir],env,project).returncode
    if options.command=='slam-export':
        env,project=compose_env();require_docker()
        return compose(['run','--rm','--no-deps','-e','PYTHONPATH=/workspace/runtime:/workspace/app:/workspace/benchmark','tools','python3','-m','uw_benchmark.slam_export',options.run_id],env,project).returncode
    if options.command == "porth":
        from .configuration import prepare_porth
        options.config = prepare_porth(options)
    if options.command=='m3-acceptance':
        return subprocess.run([sys.executable,'-m','uw_benchmark.m3_campaign','--phase',options.phase,'--cases',*options.cases,*(['--continue-on-failure'] if options.continue_on_failure else [])],env=source_env()).returncode
    if options.command=='m3-status':
        env,_=compose_env()
        return subprocess.run([sys.executable,'-m','uw_app.m3_status',env['UW_DATA_ROOT']],env=source_env()).returncode
    if options.command=='m2-status':
        env,_=compose_env()
        return subprocess.run([sys.executable,'-m','uw_app.m2_status',env['UW_DATA_ROOT']],env=source_env()).returncode
    if options.command=='m2-acceptance':
        return subprocess.run([sys.executable,'-m','uw_benchmark.m2_campaign','--phase',options.phase,'--cases',*options.cases,*(['--continue-on-failure'] if options.continue_on_failure else [])],env=source_env()).returncode
    if options.command=='acceptance':
        return subprocess.run([sys.executable,'-m','uw_benchmark.campaign','--phase',options.phase,'--cases',*options.cases,
            *(['--continue-on-failure'] if options.continue_on_failure else []),
            *(['--probe-faults'] if options.probe_faults else [])],env=source_env()).returncode
    if options.command in ('status','arm','disarm','clear-fault','command','mission','mission-cancel'):
        env,_=compose_env();require_docker()
        active=json.loads((Path(env['UW_DATA_ROOT'])/'active-session.json').read_text())
        if not (active.get('m1') or active.get('m2') or active.get('m3')) or not str(active['container']).startswith('uw-run-'):
            raise RuntimeError('No active project control simulation session')
        if active.get('m3') and options.command=='status':
            return subprocess.run([sys.executable,'-m','uw_app.m3_status',env['UW_DATA_ROOT'],'--control'],env=source_env()).returncode
        if active.get('m2'):
            print('M2 diagnostic control uses PRIVILEGED_DEBUG feedback; estimated-state control is not enabled.',file=sys.stderr)
        info=json.loads(subprocess.check_output(['docker','inspect',active['container']],text=True))[0]
        if not info['State']['Running'] or not any(m.get('Source')==str(REPO) and m['Destination']=='/workspace' for m in info['Mounts']):
            raise RuntimeError('Active container does not match this workspace')
        if options.command in ('mission','mission-cancel'):
            if not active.get('m3'):raise RuntimeError('Mission requires active M3')
            args=[options.command,'--timeout',str(options.timeout)]+(['--arm'] if options.arm else [])
            for point in options.waypoint or []:args += ['--waypoint',*[str(v) for v in point]]
            return subprocess.run(['docker','exec','--user',f"{os.getuid()}:{os.getgid()}",active['container'],'/opt/uw/entrypoint.sh','/workspace/scripts/container-cli','ros2','run','uw_tasks','mission_cli','--run-dir',active['run_dir'],*args]).returncode
        return subprocess.run(['docker','exec','--user',f"{os.getuid()}:{os.getgid()}",active['container'],
            '/opt/uw/entrypoint.sh','/workspace/scripts/container-cli','ros2','run','uw_guard','control_cli','--run-dir',active['run_dir'],options.command,
            '--seconds',str(options.seconds),'--velocity',*[str(v) for v in options.velocity]]).returncode
    if options.command == "doctor":
        return doctor()
    if options.command == "test" and options.local:
        return subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(REPO / "test"), "-v"],
                              env=source_env()).returncode
    if options.command == "validate":
        path = Path(options.config).resolve()
        code = "from uw_app.run_config import load_config; import json,sys; print(json.dumps(load_config(sys.argv[1]),indent=2))"
        if options.local:
            return subprocess.run([sys.executable, "-c", code, str(path)], env=source_env()).returncode
        if not path.is_relative_to(REPO):
            raise ValueError("Container configuration must be inside the mounted repository")
    env, project = compose_env()
    if options.command == "compose-config":
        compose(["config", "--quiet"], env, project)
        print("Compose configuration valid; no daemon or GPU execution performed.")
        return 0
    require_docker()
    Path(env["UW_DATA_ROOT"]).mkdir(parents=True, exist_ok=True)
    subprocess.run(["docker", "volume", "create", env["UW_OVERLAY_VOLUME"]],
                   check=True, stdout=subprocess.DEVNULL)
    cache = REPO / ".cache"
    cache.mkdir(exist_ok=True)
    if options.command == "build":
        from .build import build_workspace
        return build_workspace(env, project, cache)
    if options.command == "test":
        compose(["run", "--rm", "--no-deps", "tools", "/workspace/scripts/container-command", "test"], env, project)
        return 0
    if options.command == "validate":
        compose(["run", "--rm", "--no-deps", "-e", "PYTHONPATH=/workspace/app", "tools",
                 "python3", "-c", code, str(Path("/workspace") / path.relative_to(REPO))], env, project)
        return 0
    config = Path(options.config).resolve()
    if not config.is_relative_to(REPO) or not config.is_file():
        raise ValueError("Run configuration must be an existing file inside the repository")
    name = f"uw-run-{uuid.uuid4().hex[:12]}"
    env["UW_CONTAINER_NAME"] = name
    with (cache / "build.lock").open("w") as lock, tempfile.TemporaryDirectory(prefix="uw-xauth-") as temporary:
        # One worker owns the overlay and resolves the image only after the build lock.
        fcntl.flock(lock, fcntl.LOCK_EX)
        result = subprocess.run(["docker", "image", "inspect", env["UW_IMAGE"],
                                 "--format", "{{.Id}}"], capture_output=True, text=True, check=True)
        env["UW_IMAGE_ID"] = result.stdout.strip()
        compose(["run", "--rm", "--no-deps", "tools", "/workspace/scripts/container-command", "build"], env, project)
        env["UW_XAUTH_FILE"] = str(prepare_xauth(temporary))
        try:
            compose(["run", "--rm", "--no-deps", "--name", name, "sim", "ros2", "run", "uw_app", "m3_run" if options.command in ("m3","porth") else "m2_run" if options.command=="m2" else "run",
                     "--config", str(Path("/workspace") / config.relative_to(REPO))], env, name)
        finally:
            subprocess.run(["docker", "stop", "--time", "20", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            compose(["down"], env, name, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return 0


def entrypoint():
    try:
        return main()
    except KeyboardInterrupt:
        return 130
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"uw: {exc}", file=sys.stderr)
        return 1
