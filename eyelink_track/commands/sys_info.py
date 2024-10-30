from __future__ import annotations

import click


@click.command(name="sys-info")
@click.option(
    "--developer",
    help="Display information for optional dependencies.",
    is_flag=True,
)
def run(developer: bool) -> None:
    """Run sys_info() command."""
    from .. import sys_info

    sys_info(developer=developer)
