"""Record eye movements during a task run, started by the scanner trigger.

    python eyetrack_record.py --subject 01 --session 1 --run 1 --task nback

Run eyetrack_calibration first. Once the package is installed, the same command is
available as ``eyetrack_record``. See ``--help``.
"""

from eyelink_track.commands.record import run

if __name__ == "__main__":
    run()
