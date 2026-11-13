import time

from ...utils.asc import check_messages, read_messages
from ...utils.start_trigger import wait_for_start
from ..mock import MockLPT, MockTracker, TimingLog, summarize


def test_timing_log(tmp_path):
    """Test the timing log and its TSV output."""
    timing = TimingLog()
    assert timing.t0 is None
    t = time.perf_counter()
    timing("TARGET_ON", t + 0.2, code=5, x=960, y=540)
    timing("START_TRIGGER", t + 0.1, source="ttl")
    timing("WAIT_START", t)
    assert timing.t0 == t + 0.1
    timing.write(tmp_path / "timing.tsv")
    lines = (tmp_path / "timing.tsv").read_text().splitlines()
    assert lines[0] == "clock_ms\tt_rel_ms\tevent\tdetails"
    assert [line.split("\t")[2] for line in lines[1:]] == [
        "WAIT_START",
        "START_TRIGGER",
        "TARGET_ON",
    ]
    assert lines[1].split("\t")[1] == "-100.000"
    assert lines[3].split("\t")[1:] == ["100.000", "TARGET_ON", "code=5 x=960 y=540"]


def test_mock_lpt_loopback():
    """An odd code on the mock port is seen as a TTL edge, then reset."""
    lpt = MockLPT(delay=0.02)
    assert lpt._port.readPin(10) == 0
    lpt.signal(2)  # even code: bit 0 (data pin 2) stays low
    assert lpt._port.readPin(10) == 0
    time.sleep(0.05)
    lpt.signal(1)
    assert lpt._port.readPin(10) == 1
    time.sleep(0.05)
    assert lpt._port.readPin(10) == 0
    # end-to-end with the start trigger
    lpt = MockLPT()
    t_send = time.perf_counter() + 0.05

    def poll_keys():
        if t_send <= time.perf_counter():
            lpt.signal(1)
        return []

    source = wait_for_start(
        poll_keys=poll_keys, key="t", read_pin=lambda: lpt._port.readPin(10)
    )
    assert source == "ttl"


class _KeyInput:
    def __init__(self, key):
        self.__key__ = key


class _FakeGenv:
    """Graphics environment recording the calls of the mock tracker."""

    def __init__(self, keys):
        self._w, self._h = 1920, 1080
        self.keys = list(keys)
        self.calls = []
        self.tracker = None

    def setup_cal_display(self):
        self.calls.append("setup")

    def exit_cal_display(self):
        self.calls.append("exit")

    def draw_cal_target(self, x, y):
        self.calls.append(("draw", x, y))
        self.tracker.sendMessage(f"CAL_DOT_0 X={x} Y={y} T_REL_MS=1.000")

    def erase_cal_target(self):
        self.calls.append("erase")

    def get_input_key(self):
        return [_KeyInput(self.keys.pop(0))] if self.keys else []


class _Dummy:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def test_mock_tracker(tmp_path):
    """The mock tracker runs 9 targets and writes the messages as edf2asc lines."""
    timing = TimingLog()
    genv = _FakeGenv(keys=[ord("c")])
    dummy = _Dummy()
    tracker = MockTracker(dummy, genv, timing, hold=0.02, gap=0)
    genv.tracker = tracker
    tracker.sendMessage("START_TRIGGER KEY T_REL_MS=0.000")
    tracker.doTrackerSetup()
    draws = [call for call in genv.calls if call[0] == "draw"]
    assert len(draws) == 9
    assert {(x, y) for _, x, y in draws} == {
        (x, y) for x in (115, 960, 1805) for y in (92, 540, 988)
    }
    assert genv.calls.count("erase") == 9
    assert genv.calls[0] == "setup"
    assert genv.calls[-1] == "exit"
    tracker.startRecording(1, 1, 1, 1)
    tracker.stopRecording()
    tracker.close()  # passed to the dummy connection
    assert dummy.closed
    tracker.receiveDataFile("123456.EDF", str(tmp_path / "123456.EDF"))
    messages = read_messages(tmp_path / "123456.EDF")
    assert len(messages) == 10
    assert messages[0][1].startswith("START_TRIGGER")
    assert check_messages(messages, tolerance=1000)[1]
    keys = [row[2]["keys"] for row in timing.rows if row[1] == "KEYS_TO_TRACKER"]
    assert keys == ["c"]


def test_mock_tracker_escape():
    """Escape stops the mock calibration after erasing the current target."""
    timing = TimingLog()
    genv = _FakeGenv(keys=[27])
    tracker = MockTracker(_Dummy(), genv, timing, hold=0.02, gap=0)
    genv.tracker = tracker
    tracker.doTrackerSetup()
    assert genv.calls[1][0] == "draw"
    assert genv.calls[2:] == ["erase", "exit"]


def test_summarize():
    """Test the timing summary."""
    timing = TimingLog()
    assert summarize(timing) == ["No start trigger was received."]
    t = time.perf_counter()
    timing("LOOPBACK_TTL_SENT", t - 0.0005, code=1)
    timing("START_TRIGGER", t, source="ttl")
    timing("FLASH_ON", t + 0.013)
    timing("FLASH_OFF", t + 0.113)
    timing("TARGET_ON", t + 0.2, code=6, x=1805, y=540)
    timing("LPT_OUT", t + 0.2003, code=6)
    timing("TARGET_OFF", t + 1.2)
    timing("KEYS_TO_TRACKER", t + 1.3, keys="c")
    lines = summarize(timing)
    text = "\n".join(lines)
    assert lines[0] == "Start trigger: ttl (t=0)"
    assert "loopback TTL sent -> detected: 0.500 ms" in text
    assert "photodiode flash: on at +13.000 ms, on for 100.0 ms" in text
    assert "     6  1805   540    200.000      0.300   1000.0" in text
    assert "Keys that reached the tracker setup: c" in text
