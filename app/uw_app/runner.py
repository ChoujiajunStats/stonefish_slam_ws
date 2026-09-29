"""One finite run per process; timeout and shutdown use wall/steady time."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time
import uuid

import yaml

from uw_app.m1_config import load_run_config as load_config
from uw_runtime.artifacts import classify_result, create_run, event, source_snapshot, utc_now, write_json


def stop_group(process):
    for sig, timeout in ((signal.SIGINT, 10), (signal.SIGTERM, 5), (signal.SIGKILL, 5)):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            return
        deadline = time.monotonic()+timeout
        while time.monotonic() < deadline:
            process.poll()  # Reap the parent, even if descendants still own its process group.
            try:
                os.killpg(process.pid, 0)
            except ProcessLookupError:
                return
            time.sleep(0.1)


def run(config_path, repo, data_root):
    config = load_config(config_path)
    # Regression runs in the additive M2 image belong to the new M2 data campaign.
    # Original M1 image/config retains its original budget boundary.
    m2_image=Path('/opt/uw/m2-lock.sha256').exists()
    if config['schema_version']==2 or m2_image:
        baseline=0  # Loaded below from this data root, never a historical machine offset.
        used=sum(p.stat().st_size for p in (Path(data_root)/'runs').rglob('*') if p.is_file())
        # A regression in the additive survey image belongs to that existing
        # campaign; do not consume or reset the completed M3 campaign budget.
        budget_path=Path(data_root)/('porth-survey-budget.json' if Path('/opt/uw/survey-lock.sha256').exists()
            else 'porth-budget.json' if Path('/opt/uw/porth-lock.sha256').exists()
            else 'm3-budget.json' if Path('/opt/uw/m3-lock.sha256').exists() else 'm2-budget.json' if m2_image else 'm1-budget.json')
        if not budget_path.exists():
            write_json(budget_path,dict(baseline_run_bytes=used,limit_bytes=25_000_000_000,created_at=utc_now()))
        baseline=json.loads(budget_path.read_text())['baseline_run_bytes']
        estimate=4_000_000_000 if config['recording_profile']=='debug' else 100_000_000
        if used-baseline+estimate>25_000_000_000:
            raise RuntimeError(('M2' if m2_image else 'M1')+' campaign data budget would exceed 25 GB')
    output = create_run(data_root, config["run_id"])
    m1=config['schema_version']==2
    if m1:
        previous_active=Path(data_root)/'active-session.json'
        if previous_active.exists():
            previous=Path(json.loads(previous_active.read_text())['run_dir'])
            previous_replay=Path(data_root)/'runs'/previous.name/'first-native-command.json'
            if previous_replay.is_file():shutil.copy2(previous_replay,output/'previous-native-command.json')
        write_json(output/'session.json',{'run_id':output.name,'terminal_secret':uuid.uuid4().hex})
        shutil.copy2(Path(repo)/'test/m1-acceptance.yaml',output/'acceptance.yaml')
        freeze=Path(repo)/'test/m1-freeze.json'
        if freeze.exists():shutil.copy2(freeze,output/'freeze.json')
    write_json(Path(data_root)/'active-session.json',{'run_dir':str(output),
        'container':os.environ.get('UW_CONTAINER_NAME'),'namespace':config['namespace'],'m1':m1})
    manifest = {"schema_version": 1, "status": "NOT_STARTED", "started_at": utc_now(),
                "run_directory": output.name, "mode": config["mode"],
                "observation_access": config["observation_access"], "control_enabled": m1, "startup_arm_state": "DISARMED", "container": os.environ.get("UW_CONTAINER_NAME"), "process_registry_file": "process-starts.jsonl",
                "image_id": os.environ.get("UW_IMAGE_ID"),
                "seed": config["seed"], "seed_coverage": [],
                "seed_limitations": "Stonefish RNG/GPU scheduling not controlled by M0 seed",
                "clock": "patched Stonefish physics-step time; process restart reset"}
    write_json(output / "manifest.json", manifest)
    (output / "requested_config.yaml").write_bytes(Path(config_path).read_bytes())
    (output / "resolved_config.yaml").write_text(yaml.safe_dump(config, sort_keys=False))
    event(output, "created")
    process = None
    started = time.monotonic()
    previous_handlers = {}

    def interrupted(signum, frame):
        raise KeyboardInterrupt

    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            previous_handlers[sig] = signal.signal(sig, interrupted)
        manifest.update(source_snapshot(repo, output))
        middleware_path = Path(os.environ["FASTRTPS_DEFAULT_PROFILES_FILE"])
        shutil.copy2(middleware_path, output / "fastdds.xml")
        manifest["middleware"] = {
            "implementation": os.environ.get("RMW_IMPLEMENTATION"),
            "discovery_range": os.environ.get("ROS_AUTOMATIC_DISCOVERY_RANGE"),
            "profile_sha256": hashlib.sha256(middleware_path.read_bytes()).hexdigest(),
            "transport": "SHM only; container-private IPC; 32 MiB per participant",
        }
        shutil.copy2(Path(repo) / "vendor/source-lock.yaml", output / "source-lock.yaml")
        evidence = Path("/opt/uw/build-evidence.json")
        if not evidence.is_file():
            raise RuntimeError("Missing image build evidence; run inside the project image")
        built = json.loads(evidence.read_text())
        lock_sha = hashlib.sha256((output / "source-lock.yaml").read_bytes()).hexdigest()
        if built.get("source_lock_sha256") != lock_sha:
            raise RuntimeError("Source lock differs from image build; rebuild the image")
        shutil.copy2(evidence, output / "build-evidence.json")
        if Path('/opt/uw/m3-lock.sha256').exists():shutil.copy2(Path(repo)/'vendor/source-lock.m3.yaml',output/'source-lock.m3.yaml')
        m2_lock = Path('/opt/uw/m2-lock.sha256')
        if m2_lock.exists():
            m2_hash = hashlib.sha256((Path(repo)/'vendor/source-lock.m2.yaml').read_bytes()).hexdigest()
            if m2_hash != m2_lock.read_text().split()[0]:
                raise RuntimeError('Additive M2 image lock differs from workspace')
            manifest['additive_m2_source_lock_sha256'] = m2_hash
            shutil.copy2(Path(repo)/'vendor/source-lock.m2.yaml', output/'source-lock.m2.yaml')
            for extra in ('m2-upstream-evidence.json','m2-dpkg-packages.txt','m2-python-packages.json'):
                shutil.copy2(Path('/opt/uw')/extra, output/extra)

        for name in ("dpkg-packages.txt", "python-packages.json", "upstream-evidence.json", "asset-lock.json"):
            shutil.copy2(Path("/opt/uw") / name, output / name)
        if hashlib.sha256((output / "asset-lock.json").read_bytes()).hexdigest() != built["asset_lock_sha256"]:
            raise RuntimeError("Image asset lock hash mismatch")
        env = dict(os.environ, ROS_DOMAIN_ID=str(config["ros_domain_id"]),
                   ROS_LOG_DIR=str(output / "logs/ros"), RCUTILS_LOGGING_BUFFERED_STREAM="1")
        command = ["ros2", "launch", "uw_app", "control.launch.py" if m1 else "inspect.launch.py", f"run_dir:={output}"]
        manifest.update(status="RUNNING", command=command)
        write_json(output / "manifest.json", manifest)
        event(output, "launch", command=command)
        with (output / "logs/launch.log").open("w") as stream:
            process = subprocess.Popen(command, env=env, stdout=stream, stderr=subprocess.STDOUT,
                                       start_new_session=True)
            try:
                code = process.wait(timeout=config["startup_timeout_sec"]+config["duration_sec"]+30)
                manifest["launch_exit_code"] = code
                metrics_path = output / ("control-metrics.json" if m1 else "metrics.json")
                metrics = json.loads(metrics_path.read_text()) if metrics_path.exists() else {}
                exits_path = output / "process-exits.jsonl"
                exits = [json.loads(line) for line in exits_path.read_text().splitlines()] if exits_path.exists() else []
                bag_path = output / "bags/metadata.yaml"
                bag = yaml.safe_load(bag_path.read_text()) if bag_path.exists() else {}
                bag_complete = bag.get("rosbag2_bagfile_information", {}).get("message_count", 0) > 0
                if m1:
                    expected_path=output/'expected-exits.json'
                    expected=json.loads(expected_path.read_text()) if expected_path.exists() else []
                    unexpected=[e for e in exits if e['name'] not in expected and e.get('returncode')!=0]
                    finalized=config['recording_profile']=='none' or bag_complete
                    observations=True
                    if config['case_id'].startswith('load_'):
                        obs=output/'observation-metrics.json'
                        observations=obs.exists() and json.loads(obs.read_text()).get('status')=='PASS'
                    passed=code==0 and metrics.get('status')=='PASS' and not unexpected and finalized and observations
                    manifest.update(status=('COMPLETED_WITH_EXPECTED_FAULT' if expected else 'COMPLETED') if code==0 and not unexpected else 'FAILED',
                        test_verdict='PASS' if passed else 'FAIL',expected_fault_processes=expected,
                        process_exits=exits,unexpected_process_exits=unexpected,exit_reason=metrics.get('reason','Missing case metrics'))
                else:
                    manifest["status"], manifest["exit_reason"] = classify_result(
                        code, metrics, exits, config["recording_profile"] == "debug", bag_complete)
                manifest["bag_finalized_nonempty"] = bag_complete
            except subprocess.TimeoutExpired:
                manifest.update(status="TIMED_OUT", exit_reason="Wall-clock run deadline exceeded")
    except KeyboardInterrupt:
        manifest.update(status="CANCELLED", exit_reason="User/process signal")
    except Exception as exc:
        manifest.update(status="FAILED" if process else "NOT_STARTED", exit_reason=str(exc))
    finally:
        if process:
            stop_group(process)
        for sig, handler in previous_handlers.items():
            signal.signal(sig, handler)
        registry=output/'process-starts.jsonl'
        if registry.exists():manifest['processes']=[json.loads(line) for line in registry.read_text().splitlines()]
        manifest.update(finished_at=utc_now(), wall_duration_sec=time.monotonic()-started)
        write_json(output / "manifest.json", manifest)
        event(output, "finished", status=manifest["status"], reason=manifest.get("exit_reason"))
        print(json.dumps({"run_dir": str(output), "status": manifest["status"],
                          "reason": manifest.get("exit_reason")}, ensure_ascii=False, indent=2))
    return 0 if manifest.get("test_verdict")=="PASS" or manifest["status"] == "SUCCEEDED" else 1


def main(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--repo", default="/workspace")
    parser.add_argument("--data-root", default="/data")
    options = parser.parse_args(args)
    raise SystemExit(run(options.config, options.repo, options.data_root))


if __name__ == "__main__":
    main()
