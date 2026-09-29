"""Verified external asset bundles. Never imports runs or overwrites existing data."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import tempfile
from .paths import REPO


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load_lock(path=None):
    lock = json.loads((path or REPO / 'resources/porth-bundle.lock.json').read_text())
    for name in lock['files']:
        parts = PurePosixPath(name)
        if parts.is_absolute() or '..' in parts.parts or parts.as_posix() != name:
            raise ValueError('Unsafe bundle path: ' + name)
        if not (name.startswith('assets/porth_sump9_v1/') or name == 'plans/porth-survey-v14/plan.json'):
            raise ValueError('Unexpected asset location: ' + name)
    return lock


def verify(root, lock):
    root = Path(root).resolve()
    for name, item in lock['files'].items():
        path = root / name
        if not path.resolve().is_relative_to(root) or path.is_symlink():
            raise ValueError('Asset path escapes root: ' + name)
        if not path.is_file() or path.stat().st_size != item['bytes'] or digest(path) != item['sha256']:
            raise ValueError('Missing or changed asset: ' + name)


def export_bundle(source, bundle, lock):
    verify(source, lock)
    # Exclusive creation prevents replacing someone's prior bundle.
    with Path(bundle).open('xb') as stream, tarfile.open(fileobj=stream, mode='w:gz') as archive:
        for name in sorted(lock['files']):
            archive.add(Path(source) / name, arcname=name, recursive=False)


def import_bundle(destination, lock, *, source=None, bundle=None):
    if (source is None) == (bundle is None):
        raise ValueError('Choose exactly one of --source-data-root or --bundle')
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    groups = ('assets/porth_sump9_v1', 'plans/porth-survey-v14')
    # Refuse a conflict before copying anything; matching complete imports are idempotent.
    for group in groups:
        target = destination / group
        if not target.resolve().is_relative_to(destination) or target.is_symlink():
            raise ValueError('Unsafe destination: ' + group)
        if target.exists():
            verify(destination, {'files': {k: v for k, v in lock['files'].items() if k.startswith(group + '/')}})
    with tempfile.TemporaryDirectory(prefix='.asset-import-', dir=destination) as temporary:
        staging = Path(temporary)
        if source is not None:
            verify(source, lock)
            for name in lock['files']:
                out = staging / name
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(Path(source) / name, out)
        else:
            with tarfile.open(bundle, 'r:*') as archive:
                seen = set()
                for member in archive:
                    item = lock['files'].get(member.name)
                    if not member.isfile() or not item or member.name in seen or member.size != item['bytes']:
                        raise ValueError('Unexpected, duplicate, linked or wrong-size bundle member: ' + member.name)
                    seen.add(member.name)
                    out = staging / member.name
                    out.parent.mkdir(parents=True, exist_ok=True)
                    with archive.extractfile(member) as src, out.open('xb') as dst:
                        shutil.copyfileobj(src, dst)
        verify(staging, lock)
        for group in groups:
            target = destination / group
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                (staging / group).rename(target)
    verify(destination, lock)


def run(options, data):
    lock = load_lock()
    if options.action == 'verify':
        verify(options.source_data_root or data, lock)
    elif options.action == 'export':
        if options.bundle is None:
            raise ValueError('Export requires --bundle OUTPUT.tar.gz')
        export_bundle(options.source_data_root or data, options.bundle, lock)
    else:
        import_bundle(data, lock, source=options.source_data_root, bundle=options.bundle)
    print(json.dumps({'action': options.action, 'verified_files': len(lock['files']), 'data_root': str(data)}))
    return 0
