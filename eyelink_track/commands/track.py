from __future__ import annotations

from datetime import datetime
from pathlib import Path

import click


@click.command(name="track")
@click.argument(
    "fname",
    type=click.Path(exists=False, dir_okay=False, file_okay=True, path_type=Path),
    default=Path.cwd() / datetime.now().strftime("%H%M%S"),
)
@click.option("--screen", help="ID of the screen to use.", type=int, default=0)
def run(fname: Path, screen: int) -> None:
    """Run track() command."""
    from ..eye_link import Eyelink

    eye_link = Eyelink(pname=fname.parent, fname=fname.name, screen=screen)
    eye_link.calibrate()
    eye_link.win.close()
    eye_link.start()
    input(">>> Press ENTER to stop the recording.")
    eye_link.stop()
