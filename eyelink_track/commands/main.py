from __future__ import annotations

import click

from .calibration import run as calibration
from .check_asc import run as check_asc
from .gui import run as gui
from .sys_info import run as sys_info
from .track import run as track


@click.group()
def run() -> None:
    """Main package entry-point."""  # noqa: D401


run.add_command(calibration)
run.add_command(check_asc)
run.add_command(gui)
run.add_command(sys_info)
run.add_command(track)
