import time

import pytest
from click.testing import CliRunner

from ...commands.record import run
from ...utils import keyboard as kb
from ...utils.asc import read_messages


class FakeKeyboard:
    """Keyboard pressing the trigger key after a delay, or interrupted."""

    delay = 0.05
    interrupt = False

    def __init__(self, keys, device=None):
        self.keys = keys
        self.t_start = time.perf_counter()
        self.last_event_time = None
        self.closed = False

    def flush(self):  # noqa: D102
        pass

    def poll(self):  # noqa: D102
        if self.interrupt:
            raise KeyboardInterrupt
        if time.perf_counter() - self.t_start > self.delay:
            self.last_event_time = time.time() - 0.0004
            return [self.keys[0]]
        return []

    def close(self):  # noqa: D102
        self.closed = True


@pytest.fixture
def fake_keyboard(monkeypatch):
    """Replace the keyboard devices by a fake trigger box."""
    FakeKeyboard.interrupt = False
    monkeypatch.setattr(kb, "GlobalKeyboard", FakeKeyboard)
    return FakeKeyboard


ARGS = ["--subject", "01", "--session", "1", "--run", "2", "--task", "nback"]
ARGS += ["--resolution", "1920x1080", "--mock"]


def test_record_mock(tmp_path, fake_keyboard):
    """Recording starts before the trigger, which is t=0 inside the recording."""
    result = CliRunner().invoke(run, [*ARGS, "--directory", str(tmp_path)], input="\n")
    assert result.exit_code == 0, result.output
    fname = tmp_path / "sub-01_ses-1_task-nback_run-2_eyetrack_mock.asc"
    assert fname.exists()
    assert (
        tmp_path / "sub-01_ses-1_task-nback_run-2_eyetrack_mock_timing.tsv"
    ).exists()
    texts = [text for _, text in read_messages(fname)]
    assert texts[0] == "DISPLAY_COORDS 0 0 1919 1079"
    assert texts[1] == "SCREEN_GEOMETRY RES_PX=1920x1080"
    assert texts[2] == "START"
    assert texts[3].startswith("START_TRIGGER KEY T_REL_MS=0.000 WALLCLOCK=")
    assert "DETECT_DELAY_MS=" in texts[3]
    assert texts[4].startswith("RECORDING_END ELAPSED_MS=")
    lines = fname.read_text().splitlines()
    kinds = [line.split("\t")[0] for line in lines[1:]]
    assert kinds.index("START") < kinds.index("END")  # samples between START/END
    trigger = next(k for k, line in enumerate(lines) if "START_TRIGGER" in line)
    assert kinds.index("START") < trigger - 1 < kinds.index("END")
    assert "Start trigger: key (t=0)" in result.output
    assert "recording started at -" in result.output
    assert "no trigger" not in result.output


def test_record_mock_no_trigger(tmp_path, fake_keyboard):
    """Ctrl+C before the trigger still saves the recording, with a warning."""
    fake_keyboard.interrupt = True
    result = CliRunner().invoke(run, [*ARGS, "--directory", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "WARNING: no trigger was received" in result.output
    fname = tmp_path / "sub-01_ses-1_task-nback_run-2_eyetrack_mock.asc"
    texts = [text for _, text in read_messages(fname)]
    assert "START" in texts
    assert not any(text.startswith("START_TRIGGER") for text in texts)


def test_record_requires_task(tmp_path, fake_keyboard):
    """The task is required, and real recordings are never overwritten."""
    args = [a for a in ARGS if a not in ("--task", "nback", "--mock")]
    result = CliRunner().invoke(run, [*args, "--directory", str(tmp_path)])
    assert result.exit_code != 0
    assert "--task" in result.output
    (tmp_path / "sub-01_ses-1_task-nback_run-2_eyetrack.edf").touch()
    args = [a for a in ARGS if a != "--mock"]
    result = CliRunner().invoke(run, [*args, "--directory", str(tmp_path)])
    assert result.exit_code != 0
    assert "already exists" in result.output


# Run in a new Python process: the rig file must be applied before the eye-tracking
# modules are imported, which they already are in this test session.
_SCRIPT = """
import sys, time
import eyelink_track.utils.keyboard as kb

class Box:
    def __init__(self, keys, device=None):
        print(f"KEYBOARD keys={keys} device={device}")
        self.keys, self.t, self.last_event_time = keys, time.perf_counter(), None
    def flush(self):
        pass
    def poll(self):
        if time.perf_counter() - self.t > 0.05:
            self.last_event_time = time.time()
            return [self.keys[0]]
        return []
    def close(self):
        pass

kb.GlobalKeyboard = Box
from eyelink_track.commands.record import run
run(sys.argv[1:])
"""


def test_record_rig(tmp_path):
    """A rig file overrides config.py for the whole run."""
    import json
    import os
    import subprocess
    import sys

    rig = tmp_path / "mri.json"
    rig.write_text(
        json.dumps(
            {
                "_comment": "scanner",
                "START_KEY": "5",
                "RECORD_KEYBOARD": "fORP",
                "SCREEN_WIDTH_MM": 400,
                "SCREEN_HEIGHT_MM": 300,
                "SCREEN_DISTANCE_MM": [1260, 1305],
            }
        )
    )
    args = [*ARGS, "--directory", str(tmp_path), "--rig", str(rig)]
    result = subprocess.run(
        [sys.executable, "-c", _SCRIPT, *args],
        input="\n",
        capture_output=True,
        text=True,
        timeout=120,
        env=os.environ,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Rig mri.json: START_KEY='5', RECORD_KEYBOARD='fORP'" in result.stdout
    assert "KEYBOARD keys=['5'] device=fORP" in result.stdout
    fname = tmp_path / "sub-01_ses-1_task-nback_run-2_eyetrack_mock.asc"
    texts = [text for _, text in read_messages(fname)]
    assert texts[1] == (
        "SCREEN_GEOMETRY RES_PX=1920x1080 SIZE_MM=400x300 "
        "DISTANCE_MM_TOP_BOTTOM=1260,1305"
    )
    # an invalid rig file stops before anything starts
    rig.write_text(json.dumps({"SCREEN_DISTANCE": 650}))
    result = subprocess.run(
        [sys.executable, "-c", _SCRIPT, *args],
        capture_output=True,
        text=True,
        timeout=120,
        env=os.environ,
        check=False,
    )
    assert result.returncode == 2
    assert "Did you mean SCREEN_DISTANCE_MM" in result.stderr
    assert "KEYBOARD" not in result.stdout


@pytest.mark.parametrize("signame", ["SIGTERM", "SIGINT", "SIGHUP"])
def test_record_simultaneous(tmp_path, signame):
    """With --run-simultaneous, a signal stops the recording, which is saved."""
    import os
    import signal
    import subprocess
    import sys
    import threading

    def background_like():
        # as for a background job in a script: SIGINT ignored, terminal not readable
        signal.signal(signal.SIGINT, signal.SIG_IGN)

    args = [*ARGS, "--directory", str(tmp_path), "--run-simultaneous"]
    proc = subprocess.Popen(
        [sys.executable, "-c", _SCRIPT, *args],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=os.environ,
        preexec_fn=background_like,  # noqa: PLW1509
    )
    watchdog = threading.Timer(60, proc.kill)
    watchdog.start()
    try:
        lines = []
        for line in proc.stdout:
            lines.append(line)
            if line.startswith("Trigger received (t=0)"):
                break
        assert any(
            line.startswith("Recording. Waiting for the trigger") for line in lines
        )
        assert f"kill {proc.pid}" in lines[-1]
        time.sleep(0.5)
        assert proc.poll() is None  # closed stdin does not stop it
        proc.send_signal(getattr(signal, signame))
        out = "".join(lines) + proc.communicate(timeout=60)[0]
    finally:
        watchdog.cancel()
    assert proc.returncode == 0, out
    assert "Saved" in out
    fname = tmp_path / "sub-01_ses-1_task-nback_run-2_eyetrack_mock.asc"
    texts = [text for _, text in read_messages(fname)]
    assert any(text.startswith("START_TRIGGER KEY") for text in texts)
    assert texts[-1].startswith("RECORDING_END ELAPSED_MS=")
