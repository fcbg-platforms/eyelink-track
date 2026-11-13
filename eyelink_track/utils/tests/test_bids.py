import re

import pytest

from ..bids import make_edf_fname, make_temp_edf_name


def test_make_edf_fname():
    """Test the BIDS-style EDF file name."""
    assert make_edf_fname("01", "1", "1") == "sub-01_ses-1_run-1_eyetrack.edf"
    assert make_edf_fname(1, 2, 3) == "sub-1_ses-2_run-3_eyetrack.edf"
    # prefixes are accepted
    assert make_edf_fname("sub-01", "ses-pre", "run-02") == (
        "sub-01_ses-pre_run-02_eyetrack.edf"
    )
    # optional task, placed before the run as BIDS requires
    assert make_edf_fname("01", "1", "1", task="rest") == (
        "sub-01_ses-1_task-rest_run-1_eyetrack.edf"
    )
    assert make_edf_fname("01", "1", "1", suffix="eyelink") == (
        "sub-01_ses-1_run-1_eyelink.edf"
    )


@pytest.mark.parametrize(
    ("subject", "session", "run"),
    [
        ("01_a", "1", "1"),
        ("0-1", "1", "1"),
        ("", "1", "1"),
        ("01", "1 ", "a"),
        ("01", "1", "1b"),
        ("01", "1", "-1"),
    ],
)
def test_make_edf_fname_invalid(subject, session, run):
    """Test invalid BIDS labels."""
    with pytest.raises(ValueError, match="BIDS label|non-negative integer"):
        make_edf_fname(subject, session, run)


def test_make_temp_edf_name(tmp_path):
    """Test the random temporary EDF name."""
    name = make_temp_edf_name(tmp_path, 6)
    assert re.fullmatch(r"\d{6}", name)
    # all names taken
    for k in range(10):
        (tmp_path / f"{k}.EDF").touch()
    with pytest.raises(RuntimeError, match="unused"):
        make_temp_edf_name(tmp_path, 1)
    with pytest.raises(ValueError, match="between 1 and 8"):
        make_temp_edf_name(tmp_path, 9)
