import importlib.util
import json

import pytest

from ... import config as real_config
from ..rig import apply_rig, load_rig


@pytest.fixture
def config():
    """Provide a private copy of config.py, so the tests never change the real one."""
    spec = importlib.util.spec_from_file_location("config_copy", real_config.__file__)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(tmp_path, settings):
    fname = tmp_path / "rig.json"
    fname.write_text(json.dumps(settings))
    return fname


def test_load_rig(tmp_path):
    """Keys starting with '_' are comments; the file must hold a JSON object."""
    fname = _write(tmp_path, {"_comment": "MRI", "START_KEY": "5"})
    assert load_rig(fname) == {"START_KEY": "5"}
    fname.write_text("[1, 2]")
    with pytest.raises(ValueError, match="JSON object"):
        load_rig(fname)
    fname.write_text("{'START_KEY': '5'}")
    with pytest.raises(ValueError, match="not valid JSON"):
        load_rig(fname)


def test_apply_rig(config):
    """Values are converted to the config.py types; dicts are merged."""
    applied = apply_rig(
        {
            "SCREEN_WIDTH_MM": 400,
            "SCREEN_HEIGHT_MM": 300.5,
            "SCREEN_DISTANCE_MM": [1260, 1305],
            "START_KEY": "5",
            "START_TTL_PIN": None,
            "START_TTL_ACTIVE_HIGH": False,
            "START_SETUP_KEYS": ["return", "return"],
            "RECORD_KEYBOARD": "fORP",
            "PHOTODIODE_FRAMES": 1,
            "FOREGROUND_COLOR": [0.5, 0.5, 0.5],
            "SCREEN_KWARGS": {"screen": 1},
            "CAL_TRIGGER_MAP": {"0,0": 11},
        },
        config,
    )
    assert config.SCREEN_WIDTH_MM == 400.0
    assert isinstance(config.SCREEN_WIDTH_MM, float)
    assert config.SCREEN_DISTANCE_MM == (1260.0, 1305.0)
    assert config.START_KEY == "5"
    assert config.START_TTL_PIN is None
    assert config.START_TTL_ACTIVE_HIGH is False
    assert config.START_SETUP_KEYS == ("return", "return")
    assert config.RECORD_KEYBOARD == "fORP"
    assert config.FOREGROUND_COLOR == (0.5, 0.5, 0.5)
    assert config.SCREEN_KWARGS["screen"] == 1
    assert config.SCREEN_KWARGS["fullscr"] is True  # other keys kept
    assert config.CAL_TRIGGER_MAP[(0, 0)] == 11
    assert config.CAL_TRIGGER_MAP[(2, 2)] == 9
    assert "START_KEY='5'" in applied
    assert "SCREEN_DISTANCE_MM=(1260.0, 1305.0)" in applied
    # a single number is still accepted for the distance
    apply_rig({"SCREEN_DISTANCE_MM": 650}, config)
    assert config.SCREEN_DISTANCE_MM == 650.0


@pytest.mark.parametrize(
    ("settings", "match"),
    [
        ({"SCREEN_DISTANCE": 650}, "Did you mean SCREEN_DISTANCE_MM"),
        ({"start_key": "5"}, "Did you mean START_KEY"),
        ({"START_KEY": 5}, "START_KEY must be str"),
        ({"PHOTODIODE_FRAMES": 1.5}, "PHOTODIODE_FRAMES must be int"),
        ({"START_TTL_ACTIVE_HIGH": 1}, "must be bool"),
        ({"SCREEN_DISTANCE_MM": [1260]}, "SCREEN_DISTANCE_MM must be"),
        ({"FOREGROUND_COLOR": [0, 0]}, "FOREGROUND_COLOR must be"),
        ({"SCREEN_KWARGS": 1}, "JSON object"),
        ({"CAL_TRIGGER_MAP": {"top": 1}}, "row,col"),
        ({"CAL_TRIGGER_MAP": {"5,5": 1}}, "no entry"),
        ({"CAL_TRIGGER_MAP": {"0,0": "1"}}, "integer"),
    ],
)
def test_apply_rig_invalid(config, settings, match):
    """Invalid settings are refused with a clear message."""
    with pytest.raises(ValueError, match=match):
        apply_rig(settings, config)


def test_apply_rig_all_or_nothing(config):
    """Nothing changes if one setting is invalid."""
    with pytest.raises(ValueError, match="PHOTODIODE_FRAMES"):
        apply_rig({"START_KEY": "5", "PHOTODIODE_FRAMES": "two"}, config)
    assert config.START_KEY == real_config.START_KEY
