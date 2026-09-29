"""Validate/override Porth launch requests using container-owned YAML support."""
import json
from pathlib import Path
import uuid
from .paths import REPO
from .environment import compose, compose_env, require_docker


def prepare_porth(options):
    path = Path(options.config).resolve()
    if not path.is_relative_to(REPO) or not path.is_file():
        raise ValueError("Porth config must be an existing repository file")
    if not options.arm and options.water_jerlov is None:
        return str(path)
    env, project = compose_env()
    require_docker()
    Path(env["UW_DATA_ROOT"]).mkdir(parents=True, exist_ok=True)
    code = """
import sys, yaml
p, arm, water = sys.argv[1:]
c = yaml.safe_load(open(p))
if c.get('scene_profile') != 'porth_sump9': raise ValueError('Explicit Porth config required')
if arm == 'true': c.update(execute_path=True, evaluation_phase='diagnostic')
if water != 'null':
    if c.get('survey_profile') != 'known_route_capture_v1': raise ValueError('Water override requires survey')
    c['survey_water_jerlov'] = float(water)
print(yaml.safe_dump(c))
"""
    result = compose(["run", "--rm", "--no-deps", "tools", "python3", "-c", code,
                      str(Path("/workspace") / path.relative_to(REPO)),
                      json.dumps(options.arm), json.dumps(options.water_jerlov)],
                     env, project, capture_output=True, text=True)
    generated = REPO / ".cache/porth" / ("request-" + uuid.uuid4().hex + ".yaml")
    generated.parent.mkdir(parents=True, exist_ok=True)
    generated.write_text(result.stdout)
    return str(generated)
