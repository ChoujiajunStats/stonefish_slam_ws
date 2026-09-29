"""Read-only persisted map inspection, independent of launch composition."""
import hashlib
import json
import sqlite3
from pathlib import Path


def inspect_database(path):
    """Reopen the cleanly closed SQLite DB, including graph and sensor payloads."""
    path=Path(path)
    with sqlite3.connect(f'file:{path}?mode=ro',uri=True) as db:
        integrity=db.execute('PRAGMA integrity_check').fetchone()[0]
        tables={x[0] for x in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        rows={name:db.execute('SELECT COUNT(*) FROM "'+name+'"').fetchone()[0] for name in ('Node','Link','Data') if name in tables}
        sizes={}
        if 'Data' in tables:
            columns={x[1] for x in db.execute('PRAGMA table_info(Data)')}
            for name in ('image','depth','calibration','grid_obstacles'):
                if name in columns:sizes[name]=db.execute('SELECT COALESCE(SUM(LENGTH("'+name+'")),0) FROM Data').fetchone()[0]
    return dict(integrity=integrity,rows=rows,payload_bytes=sizes,size_bytes=path.stat().st_size,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),reopened_read_only=True,
        passed=integrity=='ok' and rows.get('Node',0)>0 and sizes.get('image',0)>0)

def inspect_orb_output(out):
    out = Path(out)
    files=['orb-final.json','orb-sparse-map.ply','orb-keyframes-body.jsonl','orb-optimized-camera-tum.txt','orb-atlas.osa','orb-frames.jsonl']
    missing=[p for p in files if not (out/p).is_file() or not (out/p).stat().st_size]
    final=json.loads((out/'orb-final.json').read_text()) if (out/'orb-final.json').exists() else {}
    return dict(passed=not missing and final.get('shutdown_completed') and final.get('keyframes',0)>=3,
        missing=missing,final=final,files={p:dict(bytes=(out/p).stat().st_size,sha256=hashlib.sha256((out/p).read_bytes()).hexdigest()) for p in files if (out/p).exists()},
        atlas_deserialization='NOT_YET_VERIFIED',product='ORB_SLAM3_SPARSE_STEREO')
