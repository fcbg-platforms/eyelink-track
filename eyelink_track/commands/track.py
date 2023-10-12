import argparse
from datetime import datetime
from pathlib import Path

from ..eye_link import Eyelink


def run():
    """Run track() command."""
    parser = argparse.ArgumentParser(
        prog=f"{__package__.split('.')[0]}-sys_info", description="track"
    )
    parser.add_argument(
        "dir",
        type=str,
        help="path to the directory where the file is saved.",
        default=Path.cwd(),
        nargs="?",
    )
    parser.add_argument(
        "fname",
        type=str,
        help="name of the EDF file.",
        default=datetime.now().strftime("%H%M%S"),
        nargs="?",
    )
    args = parser.parse_args()

    eye_link = Eyelink(args.dir, args.fname)
    eye_link.calibrate()
    eye_link.win.close()
    eye_link.start()
    input (">>> Press ENTER to stop the recording.")
    eye_link.stop()
