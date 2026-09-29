#!/usr/bin/env python3
"""Fetch only locked commits; fail on mismatched patches or reused directories."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

import yaml


def command(*args):
    return subprocess.run(args, check=True, text=True, capture_output=True).stdout.strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    lock = yaml.safe_load(args.lock.read_text())
    args.destination.mkdir(parents=True, exist_ok=True)
    evidence = []
    for repo in lock["repositories"]:
        name, sha = repo["name"], repo["commit"]
        if not re.fullmatch(r"[a-z0-9_]+", name) or not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ValueError("Unpinned or invalid repository entry")
        target = args.destination / name
        target.mkdir(exist_ok=False)
        command("git", "init", str(target))
        command("git", "-C", str(target), "remote", "add", "origin", repo["url"])
        command("git", "-C", str(target), "fetch", "--depth", "1", "origin", sha)
        command("git", "-C", str(target), "checkout", "--detach", "FETCH_HEAD")
        actual = command("git", "-C", str(target), "rev-parse", "HEAD")
        if actual != sha:
            raise ValueError(f"Commit mismatch for {name}")
        for patch in repo["patches"]:
            path = (args.lock.parent / patch["file"]).resolve()
            if not path.is_relative_to(args.lock.parent.resolve()):
                raise ValueError("Patch path escapes vendor directory")
            if hashlib.sha256(path.read_bytes()).hexdigest() != patch["sha256"]:
                raise ValueError(f"Patch hash mismatch: {path}")
            command("git", "-C", str(target), "apply", "--check", str(path))
            command("git", "-C", str(target), "apply", str(path))
        evidence.append({"name": name, "commit": actual, "patches": repo["patches"],
                         "status_after_patch": command("git", "-C", str(target), "status", "--porcelain")})
        print(f"Verified {name}@{actual}", flush=True)
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(json.dumps(evidence, indent=2)+"\n")


if __name__ == "__main__":
    main()
