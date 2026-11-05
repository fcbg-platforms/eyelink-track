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
LPT_ADDRESS = 0x2FB8
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
