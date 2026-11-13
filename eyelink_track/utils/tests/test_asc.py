from ..asc import check_messages, read_messages

# edf2asc-like excerpt: integer EDF timestamps, other line types ignored
ASC = """\
** CONVERTED FROM 123456.EDF using edfapi
MSG\t1000 DISPLAY_COORDS 0 0 1919 1079
MSG\t2000 START_TRIGGER TTL T_REL_MS=0.000 WALLCLOCK=2026-11-13T11:00:00+01:00
MSG\t2014 START_PHOTODIODE T_REL_MS=13.122
MSG\t2201 CAL_DOT_6 X=1805 Y=540 T_REL_MS=200.071
MSG\t3728 CAL_DOT_9 X=1805 Y=988 T_REL_MS=1727.666
START\t5000 \tLEFT\tRIGHT\tSAMPLES\tEVENTS
5001\t  960.1\t  540.2\t 1000.0\t...
MSG\t5000 START
"""


def test_read_messages(tmp_path):
    """Test reading MSG lines."""
    fname = tmp_path / "test.asc"
    fname.write_text(ASC)
    messages = read_messages(fname)
    assert len(messages) == 6
    assert messages[1] == (
        2000.0,
        "START_TRIGGER TTL T_REL_MS=0.000 WALLCLOCK=2026-11-13T11:00:00+01:00",
    )
    assert messages[-1] == (5000.0, "START")


def test_check_messages(tmp_path):
    """Test the comparison of T_REL_MS with the EDF timestamps."""
    fname = tmp_path / "test.asc"
    fname.write_text(ASC)
    lines, ok = check_messages(read_messages(fname))
    assert ok
    assert lines[-1] == "OK"
    assert any(line.startswith("CAL_DOT_9") for line in lines)
    # a message delayed by 50 ms
    messages = read_messages(fname)
    messages[3] = (messages[3][0] + 50, messages[3][1])
    lines, ok = check_messages(messages)
    assert not ok
    assert "exceed" in lines[-1]


def test_check_messages_invalid():
    """Test missing start trigger, missing timed messages, decreasing T_REL_MS."""
    lines, ok = check_messages([(1.0, "CAL_DOT_1 T_REL_MS=1")])
    assert not ok
    assert "No START_TRIGGER" in lines[0]
    lines, ok = check_messages([(1.0, "START_TRIGGER KEY T_REL_MS=0.000")])
    assert not ok
    assert "No message with T_REL_MS" in lines[-1]
    messages = [
        (0.0, "START_TRIGGER KEY T_REL_MS=0.000"),
        (10.0, "CAL_DOT_1 T_REL_MS=10.000"),
        (10.0, "CAL_DOT_2 T_REL_MS=9.000"),
    ]
    lines, ok = check_messages(messages)
    assert not ok
    assert any("not increasing" in line for line in lines)
