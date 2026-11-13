import time

import pytest

from ..start_trigger import wait_for_start


class FakePin:
    """Pin returning a scripted sequence of states, then the last one forever."""

    def __init__(self, states):
        self.states = list(states)
        self.n_reads = 0

    def __call__(self):  # noqa: D102
        self.n_reads += 1
        if len(self.states) > 1:
            return self.states.pop(0)
        return self.states[0]


class FakeKeys:
    """Keyboard returning scripted key lists, then nothing."""

    def __init__(self, presses):
        self.presses = list(presses)

    def __call__(self):  # noqa: D102
        return self.presses.pop(0) if self.presses else []


def _wait(**kwargs):
    kwargs.setdefault("key", "t")
    kwargs.setdefault("key_interval", 0)
    kwargs.setdefault("pin_interval", 0)
    return wait_for_start(**kwargs)


def test_key_starts():
    """The start key starts, other keys are ignored."""
    assert _wait(poll_keys=FakeKeys([[], ["a"], ["t"]])) == "key"


def test_escape_aborts():
    """Escape aborts."""
    assert _wait(poll_keys=FakeKeys([[], ["escape"]])) is None


def test_ttl_rising_edge():
    """A low to high edge starts."""
    pin = FakePin([0, 0, 0, 1])
    assert _wait(poll_keys=FakeKeys([]), read_pin=pin) == "ttl"


def test_ttl_falling_edge():
    """With active_level=0, a high to low edge starts."""
    pin = FakePin([1, 1, 0])
    assert _wait(poll_keys=FakeKeys([]), read_pin=pin, active_level=0) == "ttl"


def test_ttl_pin_resting_active():
    """A pin already at the active level must go back to rest before firing."""
    pin = FakePin([1, 1, 1, 0, 1])
    assert _wait(poll_keys=FakeKeys([]), read_pin=pin) == "ttl"
    assert pin.n_reads == 5
    # a pin stuck at the active level never fires; the key still works
    pin = FakePin([1])
    keys = FakeKeys([[]] * 20 + [["t"]])
    assert _wait(poll_keys=keys, read_pin=pin) == "key"


def test_short_pulse_between_key_polls():
    """A pulse shorter than the keyboard poll interval is not missed."""
    t0 = time.perf_counter()

    def pin():  # 2 ms pulse, 20 ms after the start
        return int(0.020 <= time.perf_counter() - t0 < 0.022)

    source = wait_for_start(
        poll_keys=FakeKeys([]), key="t", read_pin=pin, key_interval=0.01
    )
    assert source == "ttl"


def test_invalid_active_level():
    """Test invalid active level."""
    with pytest.raises(ValueError, match="0 or 1"):
        _wait(poll_keys=FakeKeys([]), active_level=2)
