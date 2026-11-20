"""Rig files: JSON files overriding config.py values for one setup (MRI, MEG...).

A rig file maps config.py names to values, e.g.::

    {
        "_comment": "3T scanner, projector + mirror",
        "SCREEN_WIDTH_MM": 400,
        "SCREEN_HEIGHT_MM": 300,
        "SCREEN_DISTANCE_MM": [1260, 1305],
        "START_KEY": "5",
        "RECORD_KEYBOARD": "fORP",
        "SCREEN_KWARGS": {"screen": 1},
    }

Only the listed names change. Keys starting with "_" are ignored (comments). Lists
become tuples. A dict is merged into the config.py dict; for CAL_TRIGGER_MAP, keys
are written "row,col", e.g. {"0,0": 11}.
"""

from __future__ import annotations

import difflib
import json
import types
import typing
from pathlib import Path

_NONE = type(None)


def load_rig(path: str | Path) -> dict:
    """Read a rig file."""
    path = Path(path)
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"{path.name} is not valid JSON: {error}") from None
    if not isinstance(settings, dict):
        raise ValueError(f"{path.name} must contain a JSON object {{...}}.")
    return {key: value for key, value in settings.items() if not key.startswith("_")}


def _describe(hint) -> str:
    return getattr(hint, "__name__", None) or str(hint).replace("typing.", "")


def _convert(name: str, value, hint):
    """Return value converted to the type hint, or raise ValueError."""
    origin = typing.get_origin(hint)
    if hint is typing.Any:
        return tuple(value) if isinstance(value, list) else value
    if origin in (types.UnionType, typing.Union):
        for arg in typing.get_args(hint):
            try:
                return _convert(name, value, arg)
            except ValueError:
                continue
        raise ValueError(f"{name} must be {_describe(hint)}, got {value!r}.")
    if hint is _NONE:
        if value is None:
            return None
    elif hint is bool:
        if isinstance(value, bool):
            return value
    elif hint is int:
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    elif hint is float:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    elif hint is str:
        if isinstance(value, str):
            return value
    elif origin is tuple:
        if isinstance(value, (list, tuple)):
            args = typing.get_args(hint)
            if len(args) == 2 and args[1] is Ellipsis:
                return tuple(_convert(name, item, args[0]) for item in value)
            if len(value) == len(args):
                return tuple(
                    _convert(name, item, arg)
                    for item, arg in zip(value, args, strict=True)
                )
    else:
        return value  # no check for other hints
    raise ValueError(f"{name} must be {_describe(hint)}, got {value!r}.")


def _hint_from_value(current):
    """Type hint for a config value without annotation."""
    if isinstance(current, tuple):
        kinds = {type(item) for item in current}
        if kinds <= {int, float}:
            return tuple[
                tuple(float if kinds == {float} else int | float for _ in current)
            ]
        return tuple[typing.Any, ...]
    if current is None:
        return typing.Any
    if isinstance(current, float):
        return float
    return type(current)


def _merge_dict(name: str, value, current: dict) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a JSON object, got {value!r}.")
    merged = dict(current)
    tuple_keys = any(isinstance(key, tuple) for key in current)
    for key, item in value.items():
        if tuple_keys:
            try:
                key = tuple(int(part) for part in key.split(","))
            except ValueError:
                raise ValueError(
                    f'{name} keys must look like "row,col", got {key!r}.'
                ) from None
            if key not in current:
                raise ValueError(f"{name} has no entry {key}.")
            if not isinstance(item, int) or isinstance(item, bool):
                raise ValueError(f"{name}[{key}] must be an integer, got {item!r}.")
        merged[key] = item
    return merged


def apply_rig(settings: dict, config) -> list[str]:
    """Override config values with the rig settings, after validating them all.

    Parameters
    ----------
    settings : dict
        Output of :func:`load_rig`.
    config : module
        The config module (``eyelink_track.config``).

    Returns
    -------
    applied : list of str
        ``NAME=value`` for each overridden setting.
    """
    names = [name for name in vars(config) if name.isupper()]
    hints = typing.get_type_hints(config)
    values = {}
    for name, value in settings.items():
        if name not in names:
            close = difflib.get_close_matches(name.upper(), names, n=1)
            hint = f" Did you mean {close[0]}?" if close else ""
            raise ValueError(f"Unknown setting {name!r} in the rig file.{hint}")
        current = getattr(config, name)
        if isinstance(current, dict):
            values[name] = _merge_dict(name, value, current)
        else:
            values[name] = _convert(
                name, value, hints.get(name, _hint_from_value(current))
            )
    for name, value in values.items():
        setattr(config, name, value)
    return [f"{name}={value!r}" for name, value in values.items()]
