import hashlib
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

import yaml

ROOT = Path(__file__).resolve().parents[1]


class RepositoryBoundaryTests(unittest.TestCase):
    def test_package_set_and_dependency_dag(self):
        manifests = list(ROOT.glob("*/package.xml"))
        dependencies = {}
        for path in manifests:
            package = ET.parse(path).getroot()
            dependencies[package.findtext("name")] = {item.text for item in package if item.tag.endswith("depend")}
        self.assertEqual(set(dependencies), {"uw_runtime", "uw_app", "uw_robot", "uw_simulations", "uw_benchmark", "uw_ui", "uw_interfaces", "uw_guard", "uw_controller", "uw_perception", "uw_localization", "uw_navigation", "uw_tasks"})
        self.assertFalse((ROOT / "package.xml").exists())

        def visit(name, visiting):
            self.assertNotIn(name, visiting, f"Dependency cycle at {name}")
            for dep in dependencies[name] & dependencies.keys():
                visit(dep, visiting | {name})
        for name in dependencies:
            visit(name, set())
        for name in ("uw_robot", "uw_simulations"):
            self.assertFalse(dependencies[name] & {"uw_app", "uw_ui", "uw_benchmark"})

    def test_upstream_commits_base_image_and_patch_hashes(self):
        lock = yaml.safe_load((ROOT / "vendor/source-lock.yaml").read_text())
        self.assertRegex(lock["base_image"], r"@sha256:[0-9a-f]{64}$")
        self.assertEqual(lock["base_image"], (ROOT / "docker/base-image.txt").read_text().strip())
        for repository in lock["repositories"]:
            self.assertRegex(repository["commit"], r"^[0-9a-f]{40}$")
            for patch in repository["patches"]:
                self.assertEqual(hashlib.sha256((ROOT / "vendor" / patch["file"]).read_bytes()).hexdigest(), patch["sha256"])

    def test_nonpackages_are_excluded(self):
        for directory in ("vendor", "config", "docker", "scripts", "test", "resources", "tools"):
            self.assertTrue((ROOT / directory / "COLCON_IGNORE").is_file())
        # The ignored research vault is optional in a source checkout.
        if (ROOT / "docs").is_dir():
            self.assertTrue((ROOT / "docs" / "COLCON_IGNORE").is_file())

    def test_no_global_home_socket_or_privileged_mount(self):
        compose = yaml.safe_load((ROOT / "docker/compose.yaml").read_text())
        for service in compose["services"].values():
            self.assertFalse(service.get("privileged", False))
            self.assertNotIn("network_mode", service)
            for volume in service["volumes"]:
                if isinstance(volume, dict):
                    self.assertNotIn("docker.sock", str(volume))
                    self.assertNotIn(volume["target"], ("/home", "/root", "/"))

    def test_document_local_links_resolve(self):
        # Only the root deployment README is part of the public checkout.
        for path in [ROOT / "README.md"]:
            for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
                if "://" in target or target.startswith("#"):
                    continue
                target = target.split("#")[0]
                self.assertTrue((path.parent / target).exists(), f"Broken link in {path}: {target}")
