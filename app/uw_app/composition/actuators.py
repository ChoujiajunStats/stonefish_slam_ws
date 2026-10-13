"""Verify the optional native actuator capability and retain its source lock."""
import hashlib
from pathlib import Path
import shutil


def record_actuator_build(repo, output, config, manifest):
    marker = Path('/opt/uw/actuators-lock.sha256')
    if config['robot_profile'] == 'bluerov2_six_disaware' and not marker.is_file():
        raise RuntimeError('Six-thruster profile requires --profile actuators (build it first)')
    if marker.is_file():
        source = Path(repo) / 'vendor/source-lock.actuators.yaml'
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if marker.read_text().split()[0] != digest:
            raise RuntimeError('Actuator patch lock/image mismatch')
        shutil.copy2(source, Path(output) / source.name)
        manifest['actuator_source_lock_sha256'] = digest
    manifest['robot_profile'] = config['robot_profile']
    manifest['active_attitude_axes'] = [] if config['controller_profile']=='disabled' else ['roll'] if config['robot_profile'] == 'bluerov2_six_disaware' else ['roll', 'pitch']
