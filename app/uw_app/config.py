"""Strict M0 configuration. No implicit activation of future capabilities."""

import math
import re
from pathlib import Path

import yaml


class ConfigError(ValueError):
    pass


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def _mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str) or key in result:
            raise ConfigError(f"Non-string or duplicate configuration key: {key!r}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)

ENUMS = {
    "mode": {"simulation_research"},
    "backend": {"stonefish"},
    "control_authority": {"project"},
    "robot_profile": {"bluerov2_heavy"},
    "scene_profile": {"empty_water"},
    "observation_profile": {"stereo_imu"},
    "controller_profile": {"disabled"},
    "state_source": {"ground_truth_debug"},
    "observation_access": {"PRIVILEGED_DEBUG"},
    "visualization": {"rviz", "none"},
    "recording_profile": {"debug", "none"},
}
KEYS = set(ENUMS) | {
    "schema_version", "run_id", "namespace", "use_sim_time", "seed",
    "ros_domain_id", "startup_timeout_sec", "duration_sec",
}


def validate_config(value):
    if not isinstance(value, dict):
        raise ConfigError("Run configuration must be a mapping")
    unknown, missing = set(value) - KEYS, KEYS - set(value)
    if unknown or missing:
        raise ConfigError(f"Unknown fields: {sorted(unknown)}; missing fields: {sorted(missing)}")
    for key, options in ENUMS.items():
        if not isinstance(value[key], str) or value[key] not in options:
            raise ConfigError(f"{key} must be one of {sorted(options)} (M0 capability limit)")
    for key in ("schema_version", "seed", "ros_domain_id"):
        if type(value[key]) is not int:
            raise ConfigError(f"{key} must be an integer, not a boolean or string")
    if value["schema_version"] != 1:
        raise ConfigError("Only schema_version 1 is supported")
    if not 0 <= value["seed"] < 2**32:
        raise ConfigError("seed must be in [0, 2**32)")
    if not 0 <= value["ros_domain_id"] <= 101:
        raise ConfigError("Use domain 0..101; concurrent workers require explicit allocation")
    if value["use_sim_time"] is not True:
        raise ConfigError("M0 requires use_sim_time: true")
    for key, pattern in (("namespace", r"[a-zA-Z][a-zA-Z0-9_]{0,47}"),
                         ("run_id", r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}")):
        if not isinstance(value[key], str) or not re.fullmatch(pattern, value[key]):
            raise ConfigError(f"Invalid {key}: {value[key]!r}")
    for key in ("startup_timeout_sec", "duration_sec"):
        if (type(value[key]) not in (int, float) or not math.isfinite(value[key])
                or not 0 < value[key] <= 86400):
            raise ConfigError(f"{key} must be finite and in (0, 86400]")
    return dict(value)


def load_config(path):
    try:
        with Path(path).open(encoding="utf-8") as stream:
            return validate_config(yaml.load(stream, Loader=UniqueKeyLoader))
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML: {exc}") from exc
