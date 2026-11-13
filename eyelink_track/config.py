from typing import Any

# PsychoPy windows constants
SCREEN_KWARGS: dict[str, Any] = dict(
    allowGUI=False,
    color=(-1, -1, -1),
    fullscr=True,
    monitor=None,
    winType="pyglet",
)

# Eye-tracker constants
FOREGROUND_COLOR = (0, 0, 0)
HOST_IP: str = "100.1.1.1"

# Calibration trigger constants
LPT_ADDRESS = "/dev/parport0"
CAL_TRIGGER_MAP = {
    (0, 0): 1,
    (0, 1): 2,
    (0, 2): 3,
    (1, 0): 4,
    (1, 1): 5,
    (1, 2): 6,
    (2, 0): 7,
    (2, 1): 8,
    (2, 2): 9,
}

# Photodiode patch (enabled with the --photodiode flag): drawn in the same flip as
# each calibration/validation target and kept on screen until the target is erased.
# Rising edge = target onset, falling edge = target offset. The corner must match
# where the (masked) sensor is mounted on the screen.
PHOTODIODE_SIZE: int = 50  # side of the square patch, in pixels
# one of "top-left", "top-right", "bottom-left", "bottom-right"
PHOTODIODE_CORNER: str = "top-left"
PHOTODIODE_COLOR = (1, 1, 1)  # white, in PsychoPy rgb (-1..1)
PHOTODIODE_FRAMES: int = 2

# Start trigger, used by eyetrack_calibration when --subject, --session and --run
# are given: the tracker setup opens on START_KEY or on a TTL, whichever comes first.
# Escape aborts. This first trigger is t=0: it is logged in the EDF as START_TRIGGER
# and the CAL_DOT messages carry T_REL_MS, their onset in ms relative to it. Later
# triggers (e.g. one per MRI volume) are ignored, and START_KEY presses are not
# passed to the tracker setup, so don't pick a key needed there (C, V, O, Enter...).
START_KEY: str = "t"  # PsychoPy key name, e.g. "t", "5", "space"
# Input pin on LPT_ADDRESS receiving the TTL: one of the status pins 10 (ACK),
# 11 (BUSY), 12 (PAPER-OUT), 13 (SELECT), 15 (ERROR); ground on pins 18-25.
# The data pins 2-9 are outputs (calibration triggers). Set to None to disable TTL.
START_TTL_PIN: int | None = 10
START_TTL_ACTIVE_HIGH: bool = True  # trigger on a low->high edge (False: high->low)
START_SETUP_KEYS: tuple[str, ...] = ("return",) # key which is used normally to access calibration by double enter

# Recording file names. The EyeLink Host only accepts short names, so the file is
# recorded under a random numeric name and renamed once downloaded:
# sub-<subject>_ses-<session>[_task-<task>]_run-<run>_eyetrack.edf
EDF_TEMP_DIGITS: int = 6
EDF_SUFFIX: str = "eyetrack"
