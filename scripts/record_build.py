#!/usr/bin/env python3
"""Record the actual image contents, including expected runtime asset hashes."""

import hashlib
import json
import os
from pathlib import Path
import platform
import yaml


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


output = Path("/opt/uw")
data = Path("/opt/uw_underlay/share/stonefish_bluerov2/data")
assets = {str(p.relative_to(data)): digest(p) for p in sorted(data.rglob("*")) if p.is_file()}
if not assets:
    raise RuntimeError("No BlueROV assets installed in underlay")
(output / "asset-lock.json").write_text(json.dumps(assets, indent=2, sort_keys=True)+"\n")
evidence = {
    "parent_image_id": os.environ.get("UW_PARENT_IMAGE_ID"), "base_image": os.environ.get("UW_BUILD_BASE") or yaml.safe_load((output / "vendor/source-lock.yaml").read_text())["base_image"], "python": platform.python_version(),
    "ros_distro": "jazzy", "underlay_built": True,
    "source_lock_sha256": digest(output / "vendor/source-lock.yaml"),
    "asset_lock_sha256": digest(output / "asset-lock.json"),
    "dpkg_manifest_sha256": digest(output / "dpkg-packages.txt"),
    "python_manifest_sha256": digest(output / "python-packages.json"),
}
(output / "build-evidence.json").write_text(json.dumps(evidence, indent=2)+"\n")
