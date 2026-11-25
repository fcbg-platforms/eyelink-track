"""Read keypresses from the keyboard devices, whatever window has the focus (macOS).

The macOS counterpart of :mod:`.keyboard`, with the same interface: used by
eyetrack_record to receive the trigger key while the task program has the focus.
Uses PsychToolbox's HID keyboard queues (``psychtoolbox``) and requires the Input
Monitoring permission for the terminal running the program.
"""

from __future__ import annotations

import ctypes
import time

from .logs import logger

_HINT_PERMISSION = (
    "Allow the terminal in System Settings > Privacy & Security > Input Monitoring, "
    "then quit and reopen the terminal"
)
# PsychoPy key names -> USB HID usage codes (keyboard page), for keys that are not a
# letter or digit. The keypad's codes come second.
_SPECIAL = {
    "return": (40, 88),
    "enter": (40, 88),
    "escape": (41,),
    "tab": (43,),
    "space": (44,),
    "minus": (45, 86),
    "equal": (46, 103),
}


def _import_hid():
    try:
        from psychtoolbox import hid
    except ImportError:
        raise RuntimeError(
            "Reading the trigger key requires the 'psychtoolbox' package. "
            "Install it with: uv pip install psychtoolbox"
        ) from None
    return hid


def _input_monitoring_denied() -> bool:
    """Whether macOS refuses this program the keys typed in other windows.

    An unknown answer (never asked) is not a refusal: macOS asks the user when the
    keyboards are first read.
    """
    try:
        iokit = ctypes.cdll.LoadLibrary(
            "/System/Library/Frameworks/IOKit.framework/IOKit"
        )
        iokit.IOHIDCheckAccess.argtypes = [ctypes.c_uint32]
        iokit.IOHIDCheckAccess.restype = ctypes.c_uint32
    except (OSError, AttributeError):
        return False  # before macOS 10.15: no such permission
    # kIOHIDRequestTypeListenEvent = 1; kIOHIDAccessTypeDenied = 1
    return iokit.IOHIDCheckAccess(1) == 1


def key_codes(name: str) -> set[int]:
    """Return the USB HID usage codes of a PsychoPy key name.

    As with evdev, the codes are physical keys (US layout positions): "5" is the 5
    key of the top row or of the keypad, "equal" the = key.
    """
    name = name.lower()
    if name in _SPECIAL:
        return set(_SPECIAL[name])
    if len(name) == 1 and "a" <= name <= "z":
        return {4 + ord(name) - ord("a")}
    if len(name) == 1 and name.isdigit():
        if name == "0":
            return {39, 98}
        return {29 + int(name), 88 + int(name)}
    if name[0] == "f" and name[1:].isdigit() and 1 <= int(name[1:]) <= 12:
        return {57 + int(name[1:])}
    raise ValueError(f"Unknown key {name!r} for the keyboard devices.")


def list_keyboards() -> list[tuple[str, str]]:
    """List the keyboards, as (PsychToolbox device index, name)."""
    hid = _import_hid()
    if _input_monitoring_denied():
        raise RuntimeError(
            f"macOS does not let this program read the keyboards. {_HINT_PERMISSION}."
        )
    indices, names, _ = hid.get_keyboard_indices()
    return [(str(int(index)), name) for index, name in zip(indices, names, strict=True)]


class GlobalKeyboard:
    """Watch keys on all keyboards (or one device), independently of window focus.

    Parameters
    ----------
    keys : list of str
        PsychoPy key names to watch, e.g. ``["t"]``, ``["5"]`` or ``["equal"]``.
    device : str | None
        Restrict to one device: its index (from ``--list-keyboards``) or part of its
        name, e.g. the trigger box. None reads every keyboard.
    """

    def __init__(self, keys: list[str], device: str | None = None) -> None:
        hid = _import_hid()
        from psychtoolbox import GetSecs

        self._get_secs = GetSecs
        self._codes = {code: name for name in keys for code in key_codes(name)}
        self.devices = [
            (index, name)
            for index, name in list_keyboards()
            if device is None or device == index or device.lower() in name.lower()
        ]
        if not self.devices:
            what = "keyboard" if device is None else f"device matching {device!r}"
            raise RuntimeError(
                f"No {what}. List the keyboards with: eyetrack_record --list-keyboards"
            )
        self._queues = []
        try:
            for index, name in self.devices:
                queue = hid.Keyboard(int(index))
                queue.queue_start()
                self._queues.append(queue)
                logger.info("Reading keys from device %s (%s).", index, name)
        except BaseException:
            self.close()
            raise
        self.last_event_time = None  # time.time clock, of the last key

    def poll(self) -> list[str]:
        """Return the watched keys pressed since the last call, without waiting."""
        pressed = []
        for queue in self._queues:
            while queue.flush():  # number of events waiting
                event, _ = queue.queue_get_event()
                code = int(event["Keycode"])
                if event["Pressed"] and code in self._codes:
                    pressed.append(self._codes[code])
                    # PsychToolbox times are on the GetSecs clock
                    self.last_event_time = time.time() - (
                        self._get_secs() - event["Time"]
                    )
        return pressed

    def flush(self) -> None:
        """Discard the keys pressed so far."""
        self.poll()
        self.last_event_time = None

    def close(self) -> None:
        """Stop and release the queues."""
        for queue in self._queues:
            try:
                queue.queue_stop()
                queue._release_queue()
            except Exception:
                pass
        self._queues = []
        self.devices = []
