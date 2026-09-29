"""Serialized source-image and project-overlay build."""
import fcntl
import subprocess
from .environment import compose


def build_workspace(env, project, cache):
    with (cache / "build.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        compose(["build", "tools"], env, project)
        env['UW_IMAGE_ID'] = subprocess.check_output(
            ['docker', 'image', 'inspect', env['UW_IMAGE'], '--format', '{{.Id}}'], text=True).strip()
        compose(["run", "--rm", "--no-deps", "tools", "/workspace/scripts/container-command", "build"], env, project)
    return 0
