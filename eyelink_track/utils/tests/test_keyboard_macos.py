import sys
from types import SimpleNamespace

import pytest

from .. import keyboard_macos as kb


def test_key_codes():
    """PsychoPy key names map to USB HID usages, digits to the row and the keypad."""
    assert kb.key_codes("t") == {23}
    assert kb.key_codes("A") == {4}
    assert kb.key_codes("5") == {34, 93}
    assert kb.key_codes("0") == {39, 98}
    assert kb.key_codes("equal") == {46, 103}
    assert kb.key_codes("return") == {40, 88}
    assert kb.key_codes("f1") == {58}
    with pytest.raises(ValueError, match="Unknown key"):
        kb.key_codes("foo")


class FakeQueue:
    """psychtoolbox.hid.Keyboard stand-in."""

    def __init__(self, index):
        self.index, self.events, self.started, self.released = index, [], False, False

    def queue_start(self):  # noqa: D102
        self.started = True

    def queue_stop(self):  # noqa: D102
        self.started = False

    def _release_queue(self):
        self.released = True

    def flush(self, flush_type=0):  # noqa: D102, ARG002
        return len(self.events)

    def queue_get_event(self, max_wait_secs=0):  # noqa: D102, ARG002
        return self.events.pop(0), len(self.events)


@pytest.fixture
def hid(monkeypatch):
    """Provide a built-in keyboard and a trigger box through a fake psychtoolbox."""
    queues = {}

    def keyboard(index):
        queues[index] = FakeQueue(index)
        return queues[index]

    fake_hid = SimpleNamespace(
        get_keyboard_indices=lambda: (
            [17.0, 20.0],
            ["Apple Internal Keyboard / Trackpad", "Current Designs, Inc. 932"],
            [{}, {}],
        ),
        Keyboard=keyboard,
    )
    fake = SimpleNamespace(hid=fake_hid, GetSecs=lambda: 1000.0)
    monkeypatch.setitem(sys.modules, "psychtoolbox", fake)
    monkeypatch.setattr(kb, "_input_monitoring_denied", lambda: False)
    return queues


def test_list_keyboards(hid, monkeypatch):  # noqa: ARG001
    """Keyboards are listed by their PsychToolbox index, unless macOS refuses."""
    assert kb.list_keyboards() == [
        ("17", "Apple Internal Keyboard / Trackpad"),
        ("20", "Current Designs, Inc. 932"),
    ]
    monkeypatch.setattr(kb, "_input_monitoring_denied", lambda: True)
    with pytest.raises(RuntimeError, match="Input Monitoring"):
        kb.list_keyboards()


def test_global_keyboard_devices(hid):
    """All keyboards are read, or only the one selected."""
    keyboard = kb.GlobalKeyboard(["t"])
    assert [index for index, _ in keyboard.devices] == ["17", "20"]
    assert all(queue.started for queue in hid.values())
    for device in ("current designs", "20"):
        keyboard = kb.GlobalKeyboard(["5"], device=device)
        assert keyboard.devices == [("20", "Current Designs, Inc. 932")]
    with pytest.raises(RuntimeError, match="list-keyboards"):
        kb.GlobalKeyboard(["t"], device="SyncBox")


def test_global_keyboard_poll(hid, monkeypatch):
    """Only key-down events of the watched keys are returned, with their time."""
    monkeypatch.setattr(kb.time, "time", lambda: 5000.0)
    keyboard = kb.GlobalKeyboard(["t"], device="current designs")
    assert keyboard.poll() == []
    box = hid[20]
    box.events = [
        {"Keycode": 23.0, "Pressed": 1, "Time": 999.5},  # t down
        {"Keycode": 23.0, "Pressed": 0, "Time": 999.6},  # t up
        {"Keycode": 34.0, "Pressed": 1, "Time": 999.8},  # 5 down, not watched
    ]
    assert keyboard.poll() == ["t"]
    assert keyboard.last_event_time == pytest.approx(4999.5)  # 0.5 s before GetSecs
    assert keyboard.poll() == []
    box.events = [{"Keycode": 23.0, "Pressed": 1, "Time": 999.9}]
    keyboard.flush()
    assert keyboard.poll() == []
    assert keyboard.last_event_time is None
    keyboard.close()
    assert box.released
    assert not box.started
    assert keyboard.devices == []


def test_global_keyboard_errors(monkeypatch):
    """A missing package gives instructions."""
    monkeypatch.setitem(sys.modules, "psychtoolbox", None)
    with pytest.raises(RuntimeError, match="uv pip install psychtoolbox"):
        kb.GlobalKeyboard(["t"])
