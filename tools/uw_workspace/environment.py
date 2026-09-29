"""Docker, isolated data root and display environment; no algorithm code."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from .paths import REPO

def doctor():
    checks = {}
    for name, command in {
        "docker_client": ["docker", "--version"],
        "compose": ["docker", "compose", "version"],
        "docker_daemon": ["docker", "info", "--format", "Docker {{.ServerVersion}}; runtimes: {{range $name, $runtime := .Runtimes}}{{$name}} {{end}}"],
        "gpu": ["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"],
        "xauth": ["xauth", "info"],
    }.items():
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=20)
            checks[name] = {"ok": result.returncode == 0,
                            "details": (result.stdout+result.stderr).strip()}
        except (OSError, subprocess.TimeoutExpired) as exc:
            checks[name] = {"ok": False, "details": str(exc)}
    checks["display"] = {"ok": bool(os.environ.get("DISPLAY")), "details": os.environ.get("DISPLAY", "unset")}
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    return 0 if all(item["ok"] for item in checks.values()) else 1


def compose_env():
    env = dict(os.environ)
    data = Path(env.get("UW_DATA_ROOT", str(Path.home() / ".local/share/stonefish-slam"))).expanduser().resolve()
    if data == REPO or data.is_relative_to(REPO) or REPO.is_relative_to(data):
        raise ValueError("UW_DATA_ROOT must be a dedicated directory outside the repository and its ancestors")
    # Never mount the complete home directory as the data root.
    if data == Path.home() or data == Path("/"):
        raise ValueError("UW_DATA_ROOT cannot be home or filesystem root")
    identity = hashlib.sha256(str(REPO).encode()).hexdigest()[:10]
    profile = env.get("UW_PROFILE", "orbslam3")
    profiles = json.loads((REPO / "docker/profiles.json").read_text())
    if profile not in profiles:
        raise ValueError(f"Unknown profile: {profile}")
    env.setdefault("UW_IMAGE", profiles[profile]["image"])
    env.update(UW_UID=str(os.getuid()), UW_GID=str(os.getgid()), UW_DATA_ROOT=str(data),
               UW_BASE_IMAGE=(REPO / "docker/base-image.txt").read_text().strip(),
               UW_BUILD_TARGET=profile,
               UW_OVERLAY_VOLUME=f"uw-overlay-{os.getuid()}-{identity}-{profile}")
    return env, f"uw-dev-{identity}"


def require_docker():
    result = subprocess.run(["docker", "info"], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("Docker daemon unavailable to this user:\n"+result.stderr.strip()+
                           "\nSee docs/runbook.md. No host permissions were modified.")


def compose(command, env, project, **kwargs):
    return subprocess.run(["docker", "compose", "--project-name", project,
                           "--file", str(REPO / "docker/compose.yaml"), *command],
                          env=env, check=True, **kwargs)


def prepare_xauth(directory):
    display = os.environ.get("DISPLAY")
    if not display or not shutil.which("xauth"):
        raise RuntimeError("Graphical Stonefish requires DISPLAY and xauth, including visualization: none")
    records = subprocess.run(["xauth", "nlist", display], capture_output=True, text=True, check=True).stdout
    if not records.strip():
        raise RuntimeError("No X11 authorization cookie for DISPLAY; configure local X11/XWayland first")
    # Copy only the selected display cookie. FamilyWild permits the container hostname.
    records = "\n".join("ffff"+line[4:] for line in records.splitlines())+"\n"
    path = Path(directory) / "Xauthority"
    path.touch(mode=0o600)
    subprocess.run(["xauth", "-f", str(path), "nmerge", "-"], input=records, text=True, check=True)
    return path

