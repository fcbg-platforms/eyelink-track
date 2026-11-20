"""--rig option: override config.py values from a JSON file for this run."""

from __future__ import annotations

import sys
from pathlib import Path

import click


def _apply_rig(ctx, param, value):
    if value is None or ctx.resilient_parsing:
        return
    from .. import config
    from ..utils.rig import apply_rig, load_rig

    # config.py values are read when the eye-tracking modules are imported, so the
    # rig file must be applied before (the commands import them lazily).
    loaded = [name for name in sys.modules if name.startswith("eyelink_track.eye_link")]
    if loaded:
        raise click.UsageError(
            f"--rig must be applied before importing {loaded[0]}; please report this."
        )
    try:
        applied = apply_rig(load_rig(value), config)
    except (OSError, ValueError) as error:
        raise click.BadParameter(str(error), ctx=ctx, param=param) from None
    click.echo(f"Rig {value.name}: {', '.join(applied) or 'no setting changed'}")


def rig_option(func):
    """Add the --rig option to a command."""
    return click.option(
        "--rig",
        type=click.Path(exists=True, dir_okay=False, path_type=Path),
        expose_value=False,
        is_eager=True,
        callback=_apply_rig,
        help=(
            "JSON file overriding config.py values for this setup, e.g. "
            '{"SCREEN_DISTANCE_MM": 650, "START_KEY": "5"}.'
        ),
    )(func)
