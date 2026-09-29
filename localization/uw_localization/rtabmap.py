"""RTAB-Map native parameters; paths and acquisition policy are explicit inputs."""
from pathlib import Path
import yaml


def prepare(out, namespace, defaults, *, long_survey=False):
    out = Path(out)
    p=yaml.safe_load(Path(defaults).read_text())
    ns=namespace
    p.update(use_sim_time=True,frame_id=ns+'/base_link',map_frame_id=ns+'/map',
        odom_frame_id='',database_path=str(out/'rtabmap.db'))
    p['Rtabmap/WorkingDirectory']=str(out)
    if long_survey:
        # Keep visual dictionary rebuilds bounded during long acquisitions.
        # Evicted working nodes remain in the database and can be retrieved.
        p.update({'Grid/CellSize':'0.20','Grid/RangeMax':'10.0','Rtabmap/DetectionRate':'1.0','Mem/STMSize':'30',
                  'Rtabmap/MemoryThr':'600','Rtabmap/TimeThr':'250'})
    path=out/'rtabmap-parameters.yaml';path.write_text(yaml.safe_dump({'/**':{'ros__parameters':p}},sort_keys=False))
    return str(path)

