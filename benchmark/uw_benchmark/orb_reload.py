"""Read-only native ORB Atlas reload, compared against the saved keyframe poses."""
import argparse,hashlib,json,subprocess
from pathlib import Path
import numpy as np
from uw_runtime.artifacts import write_json


def verify(run,report):
    run=Path(run);report=Path(report);report.mkdir(exist_ok=True)
    before=hashlib.sha256((run/'orb-atlas.osa').read_bytes()).hexdigest()
    text=(run/'orbslam3-settings.yaml').read_text()
    text='\n'.join(line for line in text.splitlines() if not line.startswith('System.SaveAtlasToFile:'))+'\nSystem.LoadAtlasFromFile: "orb-atlas"\n'
    settings=report/'reload-settings.yaml';settings.write_text(text)
    output=report/'reloaded-keyframes-euroc.txt'
    command=['ros2','run','uw_localization','orbslam3_atlas_check',str(run),str(settings),str(output)]
    with (report/'reload.log').open('w') as log:code=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=120).returncode
    result=dict(command=command,exit_code=code,original_atlas_sha256=before,source_unchanged=hashlib.sha256((run/'orb-atlas.osa').read_bytes()).hexdigest()==before,status='FAIL')
    if code==0:
        expected=np.loadtxt(run/'orb-keyframes-camera-tum.txt',ndmin=2);actual=np.loadtxt(output,ndmin=2);actual[:,0]*=1e-9
        same=actual.shape==expected.shape
        result.update(expected_keyframes=len(expected),reloaded_keyframes=len(actual))
        if same:
            difference=np.abs(actual-expected);result.update(maximum_timestamp_difference_sec=float(difference[:,0].max()),maximum_pose_component_difference=float(difference[:,1:].max()))
            if result['source_unchanged'] and difference[:,0].max()<1e-5 and difference[:,1:].max()<1e-6:result['status']='PASS'
    write_json(report/'atlas-reload.json',result);print(json.dumps(result,indent=2));return result


def main():
    p=argparse.ArgumentParser();p.add_argument('run_dir');p.add_argument('report_dir');a=p.parse_args();raise SystemExit(0 if verify(a.run_dir,a.report_dir)['status']=='PASS' else 1)
if __name__=='__main__':main()
