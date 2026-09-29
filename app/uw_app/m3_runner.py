"""M3 entrypoint to the shared finite-run evidence lifecycle."""
import argparse
from uw_app.m2_runner import run


def main():
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--repo',default='/workspace');p.add_argument('--data-root',default='/data');a=p.parse_args()
    raise SystemExit(run(a.config,a.repo,a.data_root,milestone=3))
