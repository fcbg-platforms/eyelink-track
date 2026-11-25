import sys
from types import SimpleNamespace

import pytest

from .. import keyboard as kb

# evdev is read on Linux; on macOS the module reads keyboard_macos's HID queues
pytestmark = pytest.mark.skipif(sys.platform == "darwin", reason="evdev: not macOS")

ECODES = SimpleNamespace(
    EV_KEY=1,
    KEY_ESC=1,
    KEY_5=6,
    KEY_TAB=15,
    KEY_T=20,
    KEY_ENTER=28,
    KEY_A=30,
    KEY_SPACE=57,
    KEY_F1=59,
    KEY_KP5=76,
    KEY_KPENTER=96,
    BTN_LEFT=272,
)


class FakeEvent:
    """evdev.InputEvent stand-in."""

    def __init__(self, code, value, t=100.0, type_=1):
        self.type, self.code, self.value, self._t = type_, code, value, t

    def timestamp(self):  # noqa: D102
        return self._t


class FakeDevice:
    """evdev.InputDevice stand-in."""

    def __init__(self, path, name, keys):
        self.path, self.name, self._keys = path, name, keys
        self.events = []
        self.closed = False

    def capabilities(self):  # noqa: D102
        return {ECODES.EV_KEY: self._keys} if self._keys else {}

    def read(self):  # noqa: D102
        if not self.events:
            raise BlockingIOError
        events, self.events = self.events, []
        return iter(events)

    def close(self):  # noqa: D102
        self.closed = True


@pytest.fixture
def devices(monkeypatch):
    """Provide a keyboard, a trigger box and a mouse through a fake evdev."""
    devs = {
        "/dev/input/event2": FakeDevice(
            "/dev/input/event2", "AT Translated Keyboard", [1, 6, 20, 28, 30, 57]
        ),
        "/dev/input/event5": FakeDevice(
            "/dev/input/event5", "Current Designs, Inc. fORP", [6, 20, 76]
        ),
        "/dev/input/event7": FakeDevice("/dev/input/event7", "USB Mouse", [272]),
    }
    fake = SimpleNamespace(
        ecodes=ECODES,
        list_devices=lambda: list(devs),
        InputDevice=lambda path: devs[path],
    )
    monkeypatch.setitem(sys.modules, "evdev", fake)
    monkeypatch.setattr(
        kb.select,
        "select",
        lambda r, w, x, t: ([dev for dev in r if dev.events], [], []),
    )
    return devs


def test_key_codes():
    """PsychoPy key names map to physical keys, digits to the row and the keypad."""
    assert kb.key_codes("t", ECODES) == {20}
    assert kb.key_codes("T", ECODES) == {20}
    assert kb.key_codes("5", ECODES) == {6, 76}
    assert kb.key_codes("return", ECODES) == {28, 96}
    assert kb.key_codes("space", ECODES) == {57}
    assert kb.key_codes("f1", ECODES) == {59}
    with pytest.raises(ValueError, match="Unknown key"):
        kb.key_codes("foo", ECODES)


def test_list_keyboards(devices):
    """Keyboards and the trigger box are listed, not the mouse."""
    assert kb.list_keyboards() == [
        ("/dev/input/event2", "AT Translated Keyboard"),
        ("/dev/input/event5", "Current Designs, Inc. fORP"),
    ]


def test_global_keyboard_devices(devices):
    """All devices with the key are read, or only the one selected."""
    keyboard = kb.GlobalKeyboard(["t"])
    assert [dev.name for dev in keyboard.devices] == [
        "AT Translated Keyboard",
        "Current Designs, Inc. fORP",
    ]
    assert devices["/dev/input/event7"].closed
    for device in ("fORP", "current designs", "/dev/input/event5"):
        keyboard = kb.GlobalKeyboard(["5"], device=device)
        assert [dev.path for dev in keyboard.devices] == ["/dev/input/event5"]
    with pytest.raises(RuntimeError, match="list-keyboards"):
        kb.GlobalKeyboard(["t"], device="SyncBox")
    with pytest.raises(RuntimeError, match="with the key"):
        kb.GlobalKeyboard(["f1"])


def test_global_keyboard_poll(devices):
    """Only key-down events of the watched keys are returned, with their time."""
    keyboard = kb.GlobalKeyboard(["t"])
    assert keyboard.poll() == []
    box = devices["/dev/input/event5"]
    box.events = [
        FakeEvent(20, 1, t=12.5),  # t down
        FakeEvent(20, 2, t=12.6),  # auto-repeat
        FakeEvent(20, 0, t=12.7),  # t up
        FakeEvent(6, 1, t=12.8),  # 5 down, not watched
        FakeEvent(20, 1, t=13.0, type_=4),  # not a key event
    ]
    assert keyboard.poll() == ["t"]
    assert keyboard.last_event_time == 12.5
    assert keyboard.poll() == []
    devices["/dev/input/event2"].events = [FakeEvent(20, 1, t=20.0)]
    keyboard.flush()
    assert keyboard.poll() == []
    assert keyboard.last_event_time is None
    keyboard.close()
    assert box.closed
    assert keyboard.devices == []


def test_global_keyboard_errors(monkeypatch):
    """Missing package or no readable device give instructions."""
    monkeypatch.setitem(sys.modules, "evdev", None)
    with pytest.raises(RuntimeError, match="uv pip install evdev"):
        kb.GlobalKeyboard(["t"])
    fake = SimpleNamespace(ecodes=ECODES, list_devices=list, InputDevice=None)
    monkeypatch.setitem(sys.modules, "evdev", fake)
    with pytest.raises(RuntimeError, match="'input' group"):
        kb.GlobalKeyboard(["t"])
