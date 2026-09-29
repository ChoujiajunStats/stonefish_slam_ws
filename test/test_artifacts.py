from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import tarfile
import unittest

from uw_benchmark.artifacts import classify_result, create_run, event, source_snapshot, write_json


class EvidenceContractTests(unittest.TestCase):
    def test_parallel_same_label_runs_never_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            with ThreadPoolExecutor(max_workers=8) as pool:
                paths = list(pool.map(lambda _: create_run(directory, "experiment"), range(24)))
            self.assertEqual(len(set(paths)), 24)
            self.assertTrue(all(path.is_relative_to(Path(directory)) for path in paths))

    def test_path_escape_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in ("../escape", "/absolute", "bad/name", ""):
                with self.assertRaises(ValueError):
                    create_run(directory, name)

    def test_snapshot_without_git_records_file_hashes_and_no_fake_sha(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo, output = root / "source", root / "output"
            repo.mkdir()
            output.mkdir()
            (repo / "code.py").write_text("value = 1\n")
            (repo / ".env").write_text("SECRET=redacted")
            (repo / ".env.local").write_text("SECRET=redacted")
            (repo / "identity.key").write_text("PRIVATE=redacted")
            result = source_snapshot(repo, output)
            self.assertIsNone(result["git_sha"])
            snapshot = json.loads((output / "source-state.json").read_text())
            self.assertIn("code.py", snapshot["files_sha256"])
            self.assertNotIn(".env", snapshot["files_sha256"])
            with tarfile.open(output / "source.tar.gz") as archive:
                self.assertEqual(archive.getnames(), ["code.py"])
                self.assertEqual(archive.extractfile("code.py").read(), b"value = 1\n")

    def test_event_log_appends_and_manifest_update_is_atomic(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            event(output, "created")
            event(output, "finished", status="NOT_STARTED")
            write_json(output / "manifest.json", {"status": "NOT_STARTED"})
            self.assertEqual(len((output / "events.jsonl").read_text().splitlines()), 2)
            self.assertEqual(json.loads((output / "manifest.json").read_text())["status"], "NOT_STARTED")
            self.assertFalse((output / "manifest.json.tmp").exists())

    def test_no_metrics_or_failed_launch_cannot_pass(self):
        self.assertEqual(classify_result(0, {}, [])[0], "FAILED")
        self.assertEqual(classify_result(1, {"status": "PASS"}, [])[0], "FAILED")

    def test_early_required_process_exit_overrides_pass_metrics(self):
        exits = [{"name": "observation_adapter", "before_probe_completion": True, "returncode": 0}]
        self.assertEqual(classify_result(0, {"status": "PASS"}, exits)[0], "FAILED")

    def test_requested_bag_must_finalize_nonempty(self):
        self.assertEqual(classify_result(0, {"status": "PASS"}, [], True, False)[0], "FAILED")
        self.assertEqual(classify_result(0, {"status": "PASS"}, [], True, True)[0], "SUCCEEDED")
