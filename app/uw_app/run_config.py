"""Select an explicit schema without enabling newer capabilities in older configs."""
from pathlib import Path
import yaml
from uw_app.config import UniqueKeyLoader


def load_config(path):
    value=yaml.load(Path(path).read_text(),Loader=UniqueKeyLoader)
    if isinstance(value,dict) and value.get('schema_version')==4:
        from uw_app.m3_config import load_config as loader
    elif isinstance(value,dict) and value.get('schema_version')==3:
        from uw_app.m2_config import load_config as loader
    else:
        from uw_app.m1_config import load_run_config as loader
    return loader(path)
