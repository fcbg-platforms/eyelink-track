"""Test helpers: run the calibration without an EyeLink Host or a parallel port.

- :class:`TimingLog` collects display, trigger and message times on one clock.
- :class:`MockLPT` replaces the parallel port, with data pin 2 looped back to the
  input pins.
- :class:`MockTracker` replaces the EyeLink Host: it runs a 9-point calibration
  through the graphics environment and writes the messages as edf2asc-like lines.
"""

from __future__ import annotations

import random
import statistics
import threading
import time
from pathlib import Path

from ..utils.logs import logger

# Target positions of an HV9 calibration with the default EyeLink calibration area
# (calibration_area_proportion = 0.88 0.83), as fractions of the screen size.
_HV9_X = (0.06, 0.5, 0.94)
_HV9_Y = (0.085, 0.5, 0.915)
_KEY_NAMES = {0: "junk", 13: "enter", 27: "escape", 32: "space"}


class TimingLog:
    """Collect timestamped events on the ``time.perf_counter`` clock.

    Called as ``timing(event, t=None, **fields)``; ``t`` defaults to now.
    """

    def __init__(self) -> None:
        self.t_start = time.perf_counter()
        self.rows: list[tuple[float, str, dict]] = []
        self._lock = threading.Lock()

    def __call__(self, event: str, t: float | None = None, **fields) -> None:
        """Log an event."""
        t = time.perf_counter() if t is None else t
        with self._lock:
            self.rows.append((t, event, fields))

    def clock_ms(self, t: float) -> float:
        """Convert a perf_counter time to ms since the start of the program."""
        return (t - self.t_start) * 1000

    def sorted_rows(self) -> list[tuple[float, str, dict]]:
        """Rows sorted by time."""
        with self._lock:
            return sorted(self.rows, key=lambda row: row[0])

    @property
    def t0(self) -> float | None:
        """Time of the start trigger, if received."""
        for t, event, _ in self.sorted_rows():
            if event == "START_TRIGGER":
                return t
        return None

    def write(self, path: str | Path) -> None:
        """Write the events as a TSV file."""
        t0 = self.t0
        lines = ["clock_ms\tt_rel_ms\tevent\tdetails"]
        for t, event, fields in self.sorted_rows():
            rel = "" if t0 is None else f"{(t - t0) * 1000:.3f}"
            details = " ".join(f"{key}={value}" for key, value in fields.items())
            lines.append(f"{self.clock_ms(t):.3f}\t{rel}\t{event}\t{details}")
        Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


class _LoopbackPort:
    """Data register of a parallel port, with data pin 2 wired to the input pins."""

    def __init__(self) -> None:
        self._data = 0

    def setData(self, value: int) -> None:  # noqa: N802
        self._data = int(value)

    def readPin(self, pin: int) -> int:  # noqa: N802, ARG002
        return self._data & 1


class MockLPT:
    """Stand-in for ``stimuli.trigger.ParallelPortTrigger`` on computers without LPT.

    Like the real port, a code stays on the data pins for ``delay`` seconds. Data pin
    2 (bit 0) is looped back to the input pins, so an odd code, e.g. the loopback
    start TTL, is seen as a TTL by the start trigger.
    """

    port_type = "pport"

    def __init__(self, delay: float = 0.01) -> None:
        self._port = _LoopbackPort()
        self._delay = delay

    def signal(self, value: int) -> None:
        """Set the code on the data pins, then reset it after the delay."""
        self._port.setData(value)
        timer = threading.Timer(self._delay, self._port.setData, args=(0,))
        timer.daemon = True
        timer.start()


def schedule_loopback(eye_link, delay: float, timing: TimingLog | None = None):
    """Send the start TTL (code 1, data pin 2) on the calibration port after delay.

    With a real port, data pin 2 must be wired to START_TTL_PIN. Returns the timer,
    to cancel it once the start trigger was received.
    """
    trigger = eye_link.genv._trigger

    def _send() -> None:
        if eye_link.t0 is not None:  # already started, e.g. by the key
            return
        if timing is not None:
            timing("LOOPBACK_TTL_SENT", code=1)
        trigger.signal(1)

    timer = threading.Timer(delay, _send)
    timer.daemon = True
    timer.start()
    return timer


def _key_code(key_input):
    """Extract the key code of a pylink.KeyInput (attribute name varies)."""
    for attr in ("key", "__key__", "_KeyInput__key", "keycode"):
        value = getattr(key_input, attr, None)
        if isinstance(value, int):
            return value
    for value in getattr(key_input, "__dict__", {}).values():
        if isinstance(value, int):
            return value
    return key_input


def _key_name(code) -> str:
    if code in _KEY_NAMES:
        return _KEY_NAMES[code]
    if isinstance(code, int) and 32 < code < 127:
        return chr(code)
    return str(code)


class MockTracker:
    """Stand-in for the EyeLink Host, wrapping pylink's dummy connection.

    Messages are timestamped on the stimulus PC clock (ms since the start of the
    program) and written, with the recording start and end, as edf2asc-like lines
    in place of the EDF file. ``doTrackerSetup`` runs a 9-point calibration through
    the graphics environment, as the Host would, and logs the keys that would reach
    the tracker. Other calls go to the dummy connection.
    """

    def __init__(self, tracker, genv, timing: TimingLog, hold=1.0, gap=0.5) -> None:
        self._tracker = tracker
        self._genv = genv
        self._timing = timing
        self._hold = hold
        self._gap = gap
        self._lines: list[str] = []

    def __getattr__(self, name):
        """Forward other calls to the dummy connection."""
        return getattr(self._tracker, name)

    def _stamp(self, kind: str, text: str) -> float:
        t = time.perf_counter()
        self._lines.append(f"{kind}\t{self._timing.clock_ms(t):.3f} {text}".rstrip())
        return t

    def sendMessage(self, text: str) -> int:  # noqa: N802
        """Log a message, as the Host would in the EDF."""
        self._timing("MSG", self._stamp("MSG", text), text=text)
        return 0

    def startRecording(self, *args) -> int:  # noqa: N802, ARG002
        """Mark the recording start."""
        self._timing("RECORDING_START", self._stamp("START", "(mock: no samples)"))
        return 0

    def stopRecording(self) -> None:  # noqa: N802
        """Mark the recording end."""
        self._timing("RECORDING_STOP", self._stamp("END", ""))

    def receiveDataFile(self, src: str, dst: str) -> int:  # noqa: N802
        """Write the messages to dst in place of the EDF file."""
        header = (
            f"** MOCK of {src}: messages logged by eyelink_track --mock, "
            "not an EDF conversion."
        )
        Path(dst).write_text("\n".join([header, *self._lines]) + "\n", encoding="utf-8")
        return 0

    def doTrackerSetup(self, *args, **kwargs) -> None:  # noqa: N802, ARG002
        """Run a 9-point calibration in random order through the graphics env."""
        genv = self._genv
        points = [
            (round(genv._w * fx), round(genv._h * fy)) for fy in _HV9_Y for fx in _HV9_X
        ]
        random.shuffle(points)
        logger.info(
            "Mock calibration: 9 targets, %.1f s each. Escape stops it.", self._hold
        )
        genv.setup_cal_display()
        for x, y in points:
            genv.draw_cal_target(x, y)
            go_on = self._poll_keys(self._hold)
            genv.erase_cal_target()
            if not go_on or not self._poll_keys(self._gap):
                break
        genv.exit_cal_display()

    def _poll_keys(self, duration: float) -> bool:
        """Poll the keys like the Host does. Return False on Escape."""
        deadline = time.perf_counter() + duration
        while time.perf_counter() < deadline:
            codes = [_key_code(key) for key in self._genv.get_input_key()]
            if codes:
                names = [_key_name(code) for code in codes]
                self._timing("KEYS_TO_TRACKER", keys=",".join(names))
                logger.info("Keys passed to the tracker: %s", ", ".join(names))
                if 27 in codes:
                    return False
            time.sleep(0.01)
        return True


def install_mock_tracker(eye_link, timing: TimingLog, hold=1.0, gap=0.5):
    """Replace the tracker connection of an Eyelink created with host_ip=None."""
    mock = MockTracker(eye_link.el_tracker, eye_link.genv, timing, hold, gap)
    eye_link.el_tracker = mock
    eye_link.genv._tracker = mock
    return mock


def summarize(timing: TimingLog) -> list[str]:
    """Summarize the start trigger and target timings of a run."""
    rows = timing.sorted_rows()
    t0 = timing.t0
    if t0 is None:
        return ["No start trigger was received."]

    def first_after(index: int, event: str):
        return next((row for row in rows[index + 1 :] if row[1] == event), None)

    i0 = next(k for k, row in enumerate(rows) if row[1] == "START_TRIGGER")
    source = rows[i0][2].get("source", "?")
    lines = [f"Start trigger: {source} (t=0)"]
    sent = [row for row in rows[:i0] if row[1] == "LOOPBACK_TTL_SENT"]
    if sent and source == "ttl":
        lines.append(
            f"  loopback TTL sent -> detected: {(t0 - sent[-1][0]) * 1000:.3f} ms"
        )
    flash_on = first_after(i0, "FLASH_ON")
    if flash_on is not None:
        flash_off = first_after(i0, "FLASH_OFF")
        duration = (
            ""
            if flash_off is None
            else f", on for {(flash_off[0] - flash_on[0]) * 1000:.1f} ms"
        )
        lines.append(
            f"  photodiode flash: on at +{(flash_on[0] - t0) * 1000:.3f} ms{duration}"
        )
    lines.append("Targets (stimulus PC clock, ms relative to the start trigger):")
    lines.append(
        f"  {'code':>4} {'x':>5} {'y':>5} {'onset':>10} {'LPT call':>10} {'on for':>8}"
    )
    lpt_delays = []
    for k, (t, event, fields) in enumerate(rows):
        if event != "TARGET_ON":
            continue
        lpt = first_after(k, "LPT_OUT")
        off = first_after(k, "TARGET_OFF")
        lpt_ms = None if lpt is None else (lpt[0] - t) * 1000
        if lpt_ms is not None:
            lpt_delays.append(lpt_ms)
        code, x, y = (str(fields.get(key)) for key in ("code", "x", "y"))
        lines.append(
            f"  {code:>4} {x:>5} {y:>5} {(t - t0) * 1000:>10.3f} "
            f"{'-' if lpt_ms is None else f'{lpt_ms:.3f}':>10} "
            f"{'-' if off is None else f'{(off[0] - t) * 1000:.1f}':>8}"
        )
    if lpt_delays:
        lines.append(
            "  LPT call: flip -> trigger.signal() returned (upper bound of the write "
            f"delay): median {statistics.median(lpt_delays):.3f} ms, "
            f"max {max(lpt_delays):.3f} ms"
        )
    keys = [row[2]["keys"] for row in rows if row[1] == "KEYS_TO_TRACKER"]
    if keys:
        lines.append(f"Keys that reached the tracker setup: {', '.join(keys)}")
    return lines
