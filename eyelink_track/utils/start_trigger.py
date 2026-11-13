"""Wait for a start trigger coming from the keyboard or from a TTL."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from .logs import logger

if TYPE_CHECKING:
    from collections.abc import Callable

#: Status pins of a parallel port that can be read as inputs.
INPUT_PINS: tuple[int, ...] = (10, 11, 12, 13, 15)


def wait_for_start(
    poll_keys: Callable[[], list[str]],
    key: str,
    read_pin: Callable[[], int] | None = None,
    active_level: int = 1,
    abort_key: str = "escape",
    key_interval: float = 0.002,
    pin_interval: float = 0.0002,
) -> str | None:
    """Block until the start key is pressed or a TTL edge is detected.

    Parameters
    ----------
    poll_keys : callable
        Returns the keys pressed since the last call, e.g.
        ``lambda: psychopy.event.getKeys(keyList=[key, "escape"])``.
    key : str
        Key starting the calibration.
    read_pin : callable | None
        Returns the current state (0/1) of the TTL input pin. None disables the TTL.
    active_level : int
        Level of the pin when the TTL is on. The trigger fires on the edge into this
        level, so a pin resting at the active level (e.g. an unconnected status pin
        pulled high) does not fire until it goes inactive and active again.
    abort_key : str
        Key aborting the wait.
    key_interval : float
        Seconds between two keyboard polls. The pin is polled in between.
    pin_interval : float
        Seconds slept between two pin reads. Keep it well below the TTL width.

    Returns
    -------
    source : str | None
        ``"key"`` or ``"ttl"``, or None if aborted with ``abort_key``.
    """
    if active_level not in (0, 1):
        raise ValueError("active_level must be 0 or 1.")
    previous = None
    if read_pin is not None:
        previous = int(bool(read_pin()))
        if previous == active_level:
            logger.warning(
                "The TTL input pin is already at its active level; waiting for it to "
                "return to rest before a TTL can start the calibration."
            )
    sleep = pin_interval if read_pin is not None else key_interval
    next_key_poll = 0.0
    while True:
        if read_pin is not None:
            state = int(bool(read_pin()))
            if state == active_level and previous != active_level:
                return "ttl"
            previous = state
        now = time.perf_counter()
        if next_key_poll <= now:
            next_key_poll = now + key_interval
            keys = poll_keys()
            if abort_key in keys:
                return None
            if key in keys:
                return "key"
        if sleep:
            time.sleep(sleep)
