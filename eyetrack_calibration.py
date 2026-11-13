"""Calibrate the EyeLink and record.

    python eyetrack_calibration.py --subject 01 --session 1 --run 1 [--photodiode]

Without --subject/--session/--run, the GUI opens. Once the package is installed, the
same command is available as ``eyetrack_calibration``. See ``--help``.
"""

from eyelink_track.commands.calibration import run

if __name__ == "__main__":
    run()
