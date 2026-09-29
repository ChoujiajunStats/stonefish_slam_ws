"""Deployment contracts: safe bundle handling and acyclic implementation imports."""
import ast
import hashlib
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from uw_workspace.assets import import_bundle, export_bundle, verify
from uw_workspace.environment import compose_env

ROOT = Path(__file__).resolve().parents[1]


class WorkspaceContracts(unittest.TestCase):
    def test_python_package_dependencies_are_acyclic(self):
        packages = {p.name: p for p in ROOT.glob('*/uw_*') if p.is_dir()}
        graph = {p: set() for p in packages}
        for name, directory in packages.items():
            for source in directory.rglob('*.py'):
                for node in ast.walk(ast.parse(source.read_text())):
                    imports = ([node.module] if isinstance(node, ast.ImportFrom) and node.module
                               else [a.name for a in node.names] if isinstance(node, ast.Import) else [])
                    graph[name].update(m.split('.')[0] for m in imports if m.split('.')[0] in packages and m.split('.')[0] != name)
        def visit(name, stack):
            self.assertNotIn(name, stack, f'Import cycle: {stack} -> {name}')
            for dependency in graph[name]:
                visit(dependency, stack + [name])
        for name in graph:
            visit(name, [])
        for name in ('uw_runtime', 'uw_robot', 'uw_controller', 'uw_guard', 'uw_simulations', 'uw_navigation', 'uw_perception'):
            self.assertFalse(graph[name] & {'uw_app', 'uw_benchmark', 'uw_workspace'})
        self.assertEqual(graph['uw_runtime'], set())

    def test_profiles_isolate_overlay_and_reject_broad_data_mount(self):
        with patch.dict(os.environ, {'UW_PROFILE': 'core', 'UW_DATA_ROOT': '/tmp/uw-test-data'}, clear=True):
            core, _ = compose_env()
            os.environ['UW_PROFILE'] = 'orbslam3'
            orb, _ = compose_env()
            self.assertNotEqual(core['UW_OVERLAY_VOLUME'], orb['UW_OVERLAY_VOLUME'])
            self.assertEqual(orb['UW_IMAGE'], 'stonefish-slam:orbslam3')
            for forbidden in ('/', str(ROOT), str(ROOT.parent), str(Path.home())):
                os.environ['UW_DATA_ROOT'] = forbidden
                with self.assertRaises(ValueError):
                    compose_env()

    def fixture(self, root):
        files = {}
        for name in ('assets/porth_sump9_v1/visual.obj', 'plans/porth-survey-v14/plan.json'):
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(name.encode())
            files[name] = {'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        return {'files': files}

    def test_bundle_round_trip_idempotence_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            lock = self.fixture(root / 'source')
            bundle = root / 'assets.tar.gz'
            export_bundle(root / 'source', bundle, lock)
            with self.assertRaises(FileExistsError):
                export_bundle(root / 'source', bundle, lock)
            destination = root / 'destination'
            import_bundle(destination, lock, bundle=bundle)
            import_bundle(destination, lock, bundle=bundle)
            verify(destination, lock)
            existing = destination / 'assets/porth_sump9_v1/visual.obj'
            existing.write_text('user modification')
            with self.assertRaises(ValueError):
                import_bundle(destination, lock, bundle=bundle)
            self.assertEqual(existing.read_text(), 'user modification')

    def test_invalid_archive_never_installs(self):
        for mode in ('escape', 'symlink', 'corrupt', 'missing', 'duplicate'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                lock = self.fixture(root / 'source')
                bundle = root / 'invalid.tar'
                with tarfile.open(bundle, 'w') as archive:
                    for index, name in enumerate(lock['files']):
                        if mode == 'missing': continue
                        info = tarfile.TarInfo('../escape' if mode == 'escape' else name)
                        data = (b'x' * len(name)) if mode == 'corrupt' else name.encode()
                        info.size = len(data)
                        if mode == 'symlink':
                            info.type = tarfile.SYMTYPE
                            info.linkname = '/tmp'
                        archive.addfile(info, io.BytesIO(data))
                        if mode == 'duplicate': archive.addfile(info, io.BytesIO(data))
                destination = root / 'destination'
                with self.assertRaises(ValueError):
                    import_bundle(destination, lock, bundle=bundle)
                self.assertFalse((destination / 'assets').exists())
                self.assertFalse((root / 'escape').exists())

    def test_multistage_build_needs_no_historical_parent_images(self):
        recipe = (ROOT / 'docker/Dockerfile').read_text()
        self.assertNotIn('FROM underwater-stack:', recipe)
        profiles = json.loads((ROOT / 'docker/profiles.json').read_text())
        for name in profiles:
            self.assertIn(' AS ' + name + '\n', recipe)
        self.assertEqual(hashlib.sha256((ROOT / 'docker/fastdds.xml').read_bytes()).hexdigest(),
                         'ca6961088346410f2e4770396caecb17ade8848974bfa6b427a31d7d307f53f7')
