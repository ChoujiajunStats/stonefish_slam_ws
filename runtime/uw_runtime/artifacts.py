"""Run evidence without ROS imports; creation is exclusive and paths are bounded."""

from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
import uuid


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix+".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True)+"\n")
    os.replace(temporary, path)


def create_run(data_root, run_id):
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", run_id):
        raise ValueError("Unsafe run_id")
    root = Path(data_root).expanduser().resolve()
    runs = root / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    name = f"{run_id}--{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}--{uuid.uuid4().hex[:12]}"
    output = runs / name
    output.mkdir(exist_ok=False)
    for child in ("logs", "figures"):
        (output / child).mkdir()
    return output


def source_snapshot(repo, output):
    repo = Path(repo).resolve()

    def git(*args):
        result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
        return result.stdout.strip() if result.returncode == 0 else None

    sha = git("rev-parse", "HEAD")
    status = git("status", "--porcelain")
    diff = git("diff", "--binary", "HEAD") if sha else None
    if diff:
        (Path(output) / "source-dirty.diff").write_text(diff+"\n")
    hashes = {}
    excluded = {".git", ".cache", "__pycache__", "build", "install", "log", ".pytest_cache"}
    with tarfile.open(Path(output) / "source.tar.gz", "w:gz") as archive:
        for directory, dirs, files in os.walk(repo):
            dirs[:] = sorted(d for d in dirs if d not in excluded and not d.endswith(".egg-info"))
            for filename in sorted(files):
                path = Path(directory) / filename
                if (filename == ".env" or filename.startswith(".env.") or
                        path.suffix in {".key", ".pem"} or path.is_symlink()):
                    continue
                relative = str(path.relative_to(repo))
                content = path.read_bytes()
                hashes[relative] = hashlib.sha256(content).hexdigest()
                entry = tarfile.TarInfo(relative)
                entry.size = len(content)
                entry.mode = path.stat().st_mode & 0o777
                archive.addfile(entry, io.BytesIO(content))
    snapshot = {"git_sha": sha, "git_status": status, "files_sha256": hashes}
    write_json(Path(output) / "source-state.json", snapshot)
    return {"git_sha": sha, "dirty": bool(status) if status is not None else None,
            "source_archive_sha256": hashlib.sha256((Path(output) / "source.tar.gz").read_bytes()).hexdigest(),
            "source_state_sha256": hashlib.sha256((Path(output) / "source-state.json").read_bytes()).hexdigest()}


def event(output, name, **details):
    with (Path(output) / "events.jsonl").open("a") as stream:
        stream.write(json.dumps({"time": utc_now(), "event": name, **details})+"\n")


def classify_result(launch_code, metrics, exits, recording_required=False, bag_complete=False):
    """Absence of acceptance evidence is failure, even with a zero launch exit."""
    if launch_code != 0:
        return "FAILED", f"Launch exited with code {launch_code}"
    if any(e.get("returncode", 0) != 0 for e in exits):
        return "FAILED", "A recorded process exited nonzero, including after probe completion"
    if any(e.get("before_probe_completion") and e["name"] != "m0_probe" for e in exits):
        return "FAILED", "Required process exited before acceptance completed"
    if metrics.get("status") != "PASS":
        return "FAILED", metrics.get("reason", "Launch exited without completed M0 metrics")
    if recording_required and not bag_complete:
        return "FAILED", "Recording requested but finalized nonempty bag metadata is missing"
    return "SUCCEEDED", metrics.get("reason", "Finite M0 observation window completed")
