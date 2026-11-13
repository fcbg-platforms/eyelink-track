from __future__ import annotations

from pathlib import Path

import click


@click.command(name="check-asc")
@click.argument("fname", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--tolerance",
    type=float,
    default=3.0,
    show_default=True,
    help="Accepted spread of EDF time - T_REL_MS, in ms.",
)
def run(fname: Path, tolerance: float) -> None:
    """Check the timing messages of an EDF converted with edf2asc (or a --mock file).

    Compares T_REL_MS, measured on the stimulus PC, with the EDF timestamps relative
    to START_TRIGGER.
    """
    from ..utils.asc import check_messages, read_messages

    lines, ok = check_messages(read_messages(fname), tolerance=tolerance)
    click.echo("\n".join(lines))
    if not ok:
        raise SystemExit(1)
