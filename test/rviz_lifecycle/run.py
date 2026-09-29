#!/usr/bin/env python3
"""Real RViz ownership regression in an isolated container; no host ROS installation."""
from pathlib import Path
import os,runpy,subprocess,sys,tempfile
repo=Path(__file__).resolve().parents[2];uw=runpy.run_path(str(repo/'scripts/uw'))
with tempfile.TemporaryDirectory(prefix='uw-rviz-lifecycle-') as tmp:
 auth=uw['prepare_xauth'](tmp)
 cmd=['docker','run','--rm','--gpus','all','--ipc','private','--network','none','--shm-size','512m','-v',str(repo)+':/workspace:ro','-v','/tmp/.X11-unix:/tmp/.X11-unix:ro','-v',str(auth)+':/tmp/uw.Xauthority:ro','-e','DISPLAY='+os.environ['DISPLAY'],'-e','XAUTHORITY=/tmp/uw.Xauthority','-e','QT_X11_NO_MITSHM=1','-e','NVIDIA_DRIVER_CAPABILITIES=graphics,utility,compute,display','-e','ROS_DOMAIN_ID=42','-e','ROS_AUTOMATIC_DISCOVERY_RANGE=SYSTEM_DEFAULT','-e','RMW_IMPLEMENTATION=rmw_fastrtps_cpp','-e','FASTRTPS_DEFAULT_PROFILES_FILE=/workspace/docker/fastdds.xml',sys.argv[1],'bash','-c','cmake -S /workspace/test/rviz_lifecycle -B /tmp/lifecycle && cmake --build /tmp/lifecycle -j4 && /tmp/lifecycle/view_manager_ownership']
 if '--memcheck' in sys.argv: cmd[-1]=cmd[-1].replace('&& /tmp/lifecycle/view_manager_ownership','&& valgrind --leak-check=no --error-limit=no --num-callers=20 --error-exitcode=99 /tmp/lifecycle/view_manager_ownership')
 raise SystemExit(subprocess.run(cmd).returncode)
