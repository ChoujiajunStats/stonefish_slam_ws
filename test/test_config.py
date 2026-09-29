import copy
from pathlib import Path
import tempfile
import unittest

from uw_app.config import ConfigError, load_config, validate_config

ROOT = Path(__file__).resolve().parents[1]


class ConfigContractTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config(ROOT / "config/run.empty_water.example.yaml")

    def test_valid_config_is_explicitly_inert_and_privileged(self):
        self.assertEqual(self.config["controller_profile"], "disabled")
        self.assertEqual(self.config["observation_access"], "PRIVILEGED_DEBUG")

    def test_unknown_field_fails(self):
        with self.assertRaises(ConfigError):
            validate_config(dict(self.config, automatic_arm=True))

    def test_missing_field_fails(self):
        del self.config["use_sim_time"]
        with self.assertRaises(ConfigError):
            validate_config(self.config)

    def test_m1_and_sitl_capabilities_cannot_be_enabled(self):
        for key, value in (("controller_profile", "body_velocity_4d"),
                           ("control_authority", "ardusub"), ("mode", "sitl"),
                           ("scene_profile", "tank"), ("state_source", "openvins"),
                           ("observation_access", "SENSOR_ONLY")):
            with self.subTest(key=key), self.assertRaises(ConfigError):
                validate_config(dict(self.config, **{key: value}))

    def test_unsafe_ids_and_namespaces_fail(self):
        for key in ("run_id", "namespace"):
            for value in ("../outside", "/rov", "a/b", "", "x;touch foo", "x"*70):
                with self.subTest(key=key, value=value), self.assertRaises(ConfigError):
                    validate_config(dict(self.config, **{key: value}))

    def test_booleans_are_not_integers(self):
        for key in ("seed", "ros_domain_id", "schema_version", "duration_sec"):
            with self.subTest(key=key), self.assertRaises(ConfigError):
                validate_config(dict(self.config, **{key: True}))

    def test_unbounded_and_nonfinite_durations_fail(self):
        for value in (0, -1, float("nan"), float("inf"), 86401, "60"):
            with self.subTest(value=value), self.assertRaises(ConfigError):
                validate_config(dict(self.config, duration_sec=value))

    def test_invalid_clock_and_domain_fail(self):
        for key, value in (("use_sim_time", False), ("use_sim_time", "true"),
                           ("ros_domain_id", -1), ("ros_domain_id", 102)):
            with self.subTest(key=key, value=value), self.assertRaises(ConfigError):
                validate_config(dict(self.config, **{key: value}))

    def test_duplicate_yaml_key_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run.yaml"
            path.write_text((ROOT / "config/run.empty_water.example.yaml").read_text()+"\nseed: 3\n")
            with self.assertRaises(ConfigError):
                load_config(path)

    def test_yaml_non_string_keys_and_object_tags_fail(self):
        for contents in ("1: value", "!!python/object/apply:os.system ['false']"):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "run.yaml"
                path.write_text(contents)
                with self.assertRaises(ConfigError):
                    load_config(path)

    def test_validation_does_not_modify_request(self):
        before = copy.deepcopy(self.config)
        validate_config(self.config)
        self.assertEqual(before, self.config)
