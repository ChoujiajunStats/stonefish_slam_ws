"""Compose existing read-only ORB evaluation and native Atlas reload checks."""
import argparse
import json
from pathlib import Path
import re
from uw_benchmark.orb_evaluate import evaluate
from uw_benchmark.orb_reload import verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_id')
    options = parser.parse_args()
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]+', options.run_id):
        parser.error('Expected a run directory name, not a path')
    root = Path('/data/runs').resolve()
    run = (root / options.run_id).resolve()
    if not run.is_relative_to(root):
        parser.error('Run path escapes data root')
    manifest = json.loads((run / 'manifest.json').read_text())
    if manifest.get('slam_backend') != 'ORB_SLAM3_STEREO' or not manifest.get('orb_output_finalized'):
        parser.error('Expected a completed ORB stereo run with finalized output')
    # evaluate creates an exclusive report directory; existing evidence cannot be replaced.
    report = evaluate(run)
    return 0 if verify(run, report)['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
