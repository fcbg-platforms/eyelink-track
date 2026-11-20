"""Read keypresses from the keyboard devices, whatever window has the focus (Linux).

Used by eyetrack_record to receive the scanner trigger key while the task program
has the focus. The devices are read, not grabbed, so the task still receives the
keys. Requires the ``evdev`` package and read access to ``/dev/input/event*`` (e.g.
the user in the ``input`` group).
"""

from __future__ import annotations

import select

from .logs import logger

_HINT_PACKAGE = "Install it with: uv pip install evdev"
_HINT_PERMISSION = (
    "Add your user to the 'input' group, then log out and back in: "
    "sudo usermod -aG input $USER"
)
# PsychoPy key names -> evdev key names, for keys that are not a letter or digit
_SPECIAL = {
    "return": ("KEY_ENTER", "KEY_KPENTER"),
    "enter": ("KEY_ENTER", "KEY_KPENTER"),
    "space": ("KEY_SPACE",),
    "escape": ("KEY_ESC",),
    "tab": ("KEY_TAB",),
}


def _import_evdev():
    try:
        import evdev
    except ImportError:
        raise RuntimeError(
            f"Reading the trigger key requires the 'evdev' package. {_HINT_PACKAGE}"
        ) from None
    return evdev


def key_codes(name: str, ecodes) -> set[int]:
    """Return the evdev key codes of a PsychoPy key name.

    The codes are physical keys (US layout positions), which is what a USB trigger
    box sends: "5" is the 5 key of the top row or of the keypad.
    """
    name = name.lower()
    if name in _SPECIAL:
        names = _SPECIAL[name]
    elif len(name) == 1 and name.isdigit():
        names = (f"KEY_{name}", f"KEY_KP{name}")
    else:
        names = (f"KEY_{name.upper()}",)
    codes = {getattr(ecodes, item) for item in names if hasattr(ecodes, item)}
    if not codes:
        raise ValueError(f"Unknown key {name!r} for the keyboard devices.")
    return codes


def list_keyboards() -> list[tuple[str, str]]:
    """List the readable devices with letter keys, as (path, name)."""
    evdev = _import_evdev()
    keyboards = []
    for path in evdev.list_devices():
        try:
            device = evdev.InputDevice(path)
        except OSError:
            continue
        keys = device.capabilities().get(evdev.ecodes.EV_KEY, [])
        if evdev.ecodes.KEY_A in keys or evdev.ecodes.KEY_5 in keys:
            keyboards.append((device.path, device.name))
        device.close()
    return keyboards


class GlobalKeyboard:
    """Watch keys on all keyboards (or one device), independently of window focus.

    Parameters
    ----------
    keys : list of str
        PsychoPy key names to watch, e.g. ``["t"]`` or ``["5"]``.
    device : str | None
        Restrict to one device: its path (``/dev/input/event5``) or part of its
        name, e.g. the trigger box. None reads every keyboard.
    """

    def __init__(self, keys: list[str], device: str | None = None) -> None:
        evdev = _import_evdev()
        self._ecodes = evdev.ecodes
        self._codes = {
            code: name for name in keys for code in key_codes(name, evdev.ecodes)
        }
        paths = evdev.list_devices()
        if not paths:
            raise RuntimeError(f"No readable input device. {_HINT_PERMISSION}")
        self.devices = []
        for path in paths:
            try:
                dev = evdev.InputDevice(path)
            except OSError:
                continue
            caps = dev.capabilities().get(evdev.ecodes.EV_KEY, [])
            matches = device is None or device in (dev.path, dev.name)
            matches = matches or device.lower() in dev.name.lower()
            if matches and set(caps) & set(self._codes):
                self.devices.append(dev)
            else:
                dev.close()
        if not self.devices:
            what = "keyboard" if device is None else f"device matching {device!r}"
            raise RuntimeError(
                f"No readable {what} with the key(s) {keys}. {_HINT_PERMISSION}. "
                "List the keyboards with: eyetrack_record --list-keyboards"
            )
        for dev in self.devices:
            logger.info("Reading keys from %s (%s).", dev.path, dev.name)
        self.last_event_time = None  # kernel time (time.time clock) of the last key

    def poll(self) -> list[str]:
        """Return the watched keys pressed since the last call, without waiting."""
        ready, _, _ = select.select(self.devices, [], [], 0)
        pressed = []
        for dev in ready:
            try:
                events = list(dev.read())
            except (BlockingIOError, OSError):
                continue
            for event in events:
                # value 1 = key down (0 = up, 2 = auto-repeat)
                if (
                    event.type == self._ecodes.EV_KEY
                    and event.value == 1
                    and event.code in self._codes
                ):
                    pressed.append(self._codes[event.code])
                    self.last_event_time = event.timestamp()
        return pressed

    def flush(self) -> None:
        """Discard the keys pressed so far."""
        self.poll()
        self.last_event_time = None

    def close(self) -> None:
        """Close the devices."""
        for dev in self.devices:
            try:
                dev.close()
            except OSError:
                pass
        self.devices = []
