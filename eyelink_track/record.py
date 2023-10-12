from datetime import datetime

from .eye_link import Eyelink



eye_link = Eyelink(RECORD_DIR, fname)
eye_link.calibrate()
win = eye_link.win
