"""M2 finite-run lifecycle and evidence. Algorithms live in their own packages."""
import argparse,hashlib,json,os,shutil,signal,subprocess,time,uuid
from pathlib import Path
import yaml
from uw_app.m2_config import load_config
from uw_app.runner import stop_group
from uw_runtime.artifacts import create_run,write_json,source_snapshot,utc_now,event


def run(config_path,repo,data_root,milestone=2):
    if milestone==3:
        from uw_app.m3_config import load_config as loader
    else:loader=load_config
    config=loader(config_path);repo=Path(repo);data_root=Path(data_root)
    porth=config['scene_profile']=='porth_sump9'
    survey=config.get('survey_profile')=='known_route_capture_v1'
    orb=config.get('slam_profile')=='orbslam3_stereo'
    used=sum(p.stat().st_size for p in (data_root/'runs').rglob('*') if p.is_file())
    budget_path=data_root/('orbslam3-budget.json' if orb else 'porth-survey-budget.json' if survey else 'porth-budget.json' if porth else 'm3-budget.json' if Path('/opt/uw/m3-lock.sha256').exists() else f'm{milestone}-budget.json')
    if not budget_path.exists():write_json(budget_path,dict(baseline_run_bytes=used,limit_bytes=25_000_000_000,created_at=utc_now()))
    budget=json.loads(budget_path.read_text())
    estimate=int(config['duration_sec']*70_000_000) if config['recording_profile'] in ('sensors','debug') else int(config['duration_sec']*2_000_000) if survey else 150_000_000
    if used-budget['baseline_run_bytes']+estimate>budget['limit_bytes']:raise RuntimeError('Active milestone data budget would exceed 25 GB')
    if shutil.disk_usage(data_root).free<20_000_000_000:raise RuntimeError('Less than 20 GB disk free')
    output=create_run(data_root,config['run_id']);process=None;started=time.monotonic()
    if milestone==3 and (data_root/'active-session.json').exists():
        previous=json.loads((data_root/'active-session.json').read_text());old=data_root/'runs'/Path(previous['run_dir']).name/'first-request.cdr'
        if old.exists():shutil.copy2(old,output/'previous-request.cdr')
    write_json(output/'session.json',dict(run_id=output.name,terminal_secret=uuid.uuid4().hex))
    write_json(data_root/'active-session.json',dict(run_dir=str(output),container=os.environ.get('UW_CONTAINER_NAME'),namespace=config['namespace'],m1=False,m2=milestone==2,m3=milestone==3))
    (output/'requested_config.yaml').write_bytes(Path(config_path).read_bytes())
    (output/'resolved_config.yaml').write_text(yaml.safe_dump(config,sort_keys=False))
    manifest=dict(schema_version=2,milestone=f'M{milestone}',status='NOT_STARTED',test_verdict='NOT_RUN',started_at=utc_now(),
        run_directory=output.name,image_id=os.environ.get('UW_IMAGE_ID'),container=os.environ.get('UW_CONTAINER_NAME'),
        state_source='OPENVINS_STEREO_IMU',evaluation_truth='PRIVILEGED_DEBUG',
        diagnostic_controller_state='PRIVILEGED_DEBUG' if milestone==2 else None,estimated_state_control=milestone==3,startup_arm_state='DISARMED',
        evaluation_phase=config['evaluation_phase'],clock='single patched Stonefish physics clock',
        seed=config['seed'],seed_coverage=['fixture_texture_only'],data_budget=budget)
    write_json(output/'manifest.json',manifest)
    previous={}
    def interrupt(*_):raise KeyboardInterrupt
    try:
        for sig in (signal.SIGINT,signal.SIGTERM):previous[sig]=signal.signal(sig,interrupt)
        manifest.update(source_snapshot(repo,output))
        for name in ('source-lock.yaml','source-lock.m2.yaml'):shutil.copy2(repo/'vendor'/name,output/name)
        lock=hashlib.sha256((output/'source-lock.m2.yaml').read_bytes()).hexdigest()
        built=Path('/opt/uw/m2-lock.sha256').read_text().split()[0]
        if lock!=built:raise RuntimeError('M2 lock differs from image; rebuild required')
        manifest['m2_source_lock_sha256']=lock
        if milestone==3:
            shutil.copy2(repo/'vendor/source-lock.m3.yaml',output/'source-lock.m3.yaml')
            m3lock=hashlib.sha256((output/'source-lock.m3.yaml').read_bytes()).hexdigest()
            if m3lock!=Path('/opt/uw/m3-lock.sha256').read_text().split()[0]:raise RuntimeError('M3 parent lock/image mismatch')
            manifest['m3_source_lock_sha256']=m3lock
        if porth:
            for name in ('source-lock.porth.yaml','porth-dpkg-packages.txt'):shutil.copy2(Path('/opt/uw')/name,output/name)
            lock=hashlib.sha256((repo/'vendor/source-lock.porth.yaml').read_bytes()).hexdigest()
            if lock!=Path('/opt/uw/porth-lock.sha256').read_text().split()[0]:raise RuntimeError('SLAM image/lock mismatch')
            manifest.update(milestone='PORTH_SLAM_DEMO',slam_backend='RTAB-Map stereo',porth_lock_sha256=lock,explicit_path_authorization=config['execute_path'])
        if survey:
            manifest.update(milestone='PORTH_SURVEY',diagnostic_controller_state='PRIVILEGED_DEBUG',estimated_state_control=False,survey_plan_sha256=config['survey_plan_sha256'])
            if Path('/opt/uw/survey-lock.sha256').exists():
                lock=hashlib.sha256((repo/'vendor/source-lock.survey.yaml').read_bytes()).hexdigest()
                if lock!=Path('/opt/uw/survey-lock.sha256').read_text().split()[0]:raise RuntimeError('Survey patch lock/image mismatch')
                shutil.copytree('/opt/uw/survey',output/'survey-vendor')
                manifest['survey_source_lock_sha256']=lock
        if orb:
            lock=hashlib.sha256((repo/'vendor/source-lock.orbslam3.yaml').read_bytes()).hexdigest()
            if lock!=Path('/opt/uw/orbslam3-lock.sha256').read_text().split()[0]:raise RuntimeError('ORB-SLAM3 image/lock mismatch')
            shutil.copytree('/opt/uw/orbslam3',output/'orbslam3-vendor')
            binary_paths=[Path('/work/overlay/install/uw_localization/lib/uw_localization')/name for name in ('orbslam3','orbslam3_atlas_check')]
            binary_paths.append(Path('/opt/uw_src/ORB_SLAM3/lib/libORB_SLAM3.so'))
            write_json(output/'orb-binaries.json',{str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in binary_paths})
            manifest.update(slam_backend='ORB_SLAM3_STEREO',orbslam3_source_lock_sha256=lock,slam_inputs=['left_image','right_image'],auxiliary_estimator='OPENVINS_STEREO_IMU',state_source='PRIVILEGED_DEBUG',map_product='SPARSE_LANDMARKS')
        for name in ('build-evidence.json','asset-lock.json','upstream-evidence.json','m2-upstream-evidence.json','m2-dpkg-packages.txt','m2-python-packages.json'):
            shutil.copy2(Path('/opt/uw')/name,output/name)
        shutil.copy2(os.environ['FASTRTPS_DEFAULT_PROFILES_FILE'],output/'fastdds.xml')
        manifest['dds_sha256']=hashlib.sha256((output/'fastdds.xml').read_bytes()).hexdigest()
        shutil.copy2(repo/('test/orbslam3-acceptance.yaml' if orb else 'test/porth-survey-acceptance.yaml' if survey else 'test/porth-acceptance.yaml' if porth else f'test/m{milestone}-acceptance.yaml'),output/'acceptance.yaml')
        if not porth and (repo/f'test/m{milestone}-freeze.json').exists():shutil.copy2(repo/f'test/m{milestone}-freeze.json',output/'freeze.json')
        if orb and (repo/'test/orbslam3-freeze.json').exists():shutil.copy2(repo/'test/orbslam3-freeze.json',output/'freeze.json')
        if survey and not orb and (repo/'test/porth-survey-freeze.json').exists():shutil.copy2(repo/'test/porth-survey-freeze.json',output/'freeze.json')
        env=dict(os.environ,ROS_DOMAIN_ID=str(config['ros_domain_id']),ROS_LOG_DIR=str(output/'logs/ros'),RCUTILS_LOGGING_BUFFERED_STREAM='1')
        command=['ros2','launch','uw_app','navigate.launch.py' if milestone==3 else 'estimate.launch.py',f'run_dir:={output}']
        manifest.update(status='RUNNING',command=command);write_json(output/'manifest.json',manifest);event(output,'launch',command=command)
        with (output/'logs/launch.log').open('w') as stream:
            process=subprocess.Popen(command,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
            code=process.wait(timeout=config['startup_timeout_sec']+config['duration_sec']+(180 if orb else 35))
        manifest['launch_exit_code']=code
        metrics_path=output/f'm{milestone}-metrics.json';metrics=json.loads(metrics_path.read_text()) if metrics_path.exists() else {}
        exits_path=output/'process-exits.jsonl';exits=[json.loads(s) for s in exits_path.read_text().splitlines()] if exits_path.exists() else []
        expected_path=output/'expected-exits.json';expected=json.loads(expected_path.read_text()) if expected_path.exists() else []
        unexpected=[x for x in exits if x['returncode']!=0 and x['name'] not in expected]
        starts_path=output/'process-starts.jsonl'
        starts=[json.loads(s) for s in starts_path.read_text().splitlines()] if starts_path.exists() else []
        exit_accounting=bool(starts) and len(exits)==len(starts) and {x['name'] for x in exits}=={x['name'] for x in starts}
        expected_codes=all(x['returncode']==-9 for x in exits if x['name'] in expected)
        bag=output/'bags/metadata.yaml';bagmeta=yaml.safe_load(bag.read_text()) if bag.exists() else {}
        finalized=bagmeta.get('rosbag2_bagfile_information',{}).get('message_count',0)>0
        passed=code==0 and metrics.get('status')=='PASS' and not unexpected and exit_accounting and expected_codes and (config['recording_profile']=='none' or finalized)
        if porth:
            from uw_localization.artifacts import inspect_database
            if orb:
                from uw_localization.artifacts import inspect_orb_output as inspect_output
                database=inspect_output(output)
            else:database=inspect_database(output/'rtabmap.db') if (output/'rtabmap.db').exists() else {'passed':False,'reason':'No database'}
            write_json(output/'slam-database-inspection.json',database)
            slam_path=output/'slam-metrics.json';slam=json.loads(slam_path.read_text()) if slam_path.exists() else {}
            passed=passed and database['passed'] and slam.get('status')=='PASS'
            manifest.update(slam_verdict=slam.get('status','NOT_RUN'),**({'orb_output_finalized':database['passed']} if orb else {'database_reopened':database['passed']}))
        manifest.update(status=('COMPLETED_WITH_EXPECTED_FAULT' if expected else 'COMPLETED') if code==0 and not unexpected else 'FAILED',
            test_verdict='PASS' if passed else 'FAIL',process_exits=exits,expected_process_exits=expected,
            exit_accounting_complete=exit_accounting,expected_exit_codes_verified=expected_codes,
            bag_finalized_nonempty=finalized,reason=metrics.get('reason','Missing M2 metrics'))
        if porth and not passed:
            manifest['reason']='Porth checks incomplete: '+json.dumps(dict(mission=metrics.get('status','NOT_RUN'),
                slam=slam.get('status','NOT_RUN'),database=database['passed'],unexpected_exits=unexpected,
                exit_accounting=exit_accounting,bag_finalized=finalized))
    except subprocess.TimeoutExpired:manifest.update(status='TIMED_OUT',test_verdict='FAIL',reason='Finite wall timeout exceeded')
    except KeyboardInterrupt:manifest.update(status='CANCELLED',reason='Interrupted')
    except Exception as exc:manifest.update(status='FAILED',test_verdict='FAIL',reason=str(exc))
    finally:
        if process:stop_group(process)
        for sig,handler in previous.items():signal.signal(sig,handler)
        manifest['artifact_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.is_file() and p.suffix in ('.yaml','.xml','.scn','.urdf')}
        manifest.update(finished_at=utc_now(),wall_duration_sec=time.monotonic()-started)
        write_json(output/'manifest.json',manifest);event(output,'finished',status=manifest['status'],test_verdict=manifest['test_verdict'])
        print(json.dumps(dict(run_dir=str(output),**manifest),indent=2))
    return 0 if manifest['test_verdict']=='PASS' else 1


def main():
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--repo',default='/workspace');p.add_argument('--data-root',default='/data');a=p.parse_args()
    raise SystemExit(run(a.config,a.repo,a.data_root))
