"""Read-only persisted map inspection, independent of launch composition."""
import hashlib
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
