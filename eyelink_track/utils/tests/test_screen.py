import pytest

from ..screen import (
    parse_resolution,
    screen_geometry_commands,
    screen_geometry_message,
)


def test_parse_resolution():
    """Test parsing WxH."""
    assert parse_resolution("1920x1080") == (1920, 1080)
    assert parse_resolution("2560X1440") == (2560, 1440)
    for text in ("1920", "1920x", "axb", "0x1080", "1920x1080x3"):
        with pytest.raises(ValueError, match="Resolution"):
            parse_resolution(text)


def test_screen_geometry_commands():
    """Test the screen_phys_coords and screen_distance commands."""
    assert screen_geometry_commands(None, None, None) == []
    assert screen_geometry_commands(530, 300, None) == [
        "screen_phys_coords = -265.0, 150.0, 265.0, -150.0"
    ]
    # eye-to-centre distance converted to eye-to-top/bottom: hypot(600, 150) = 618.5
    assert screen_geometry_commands(530, 300, 600) == [
        "screen_phys_coords = -265.0, 150.0, 265.0, -150.0",
        "screen_distance = 618 618",
    ]
    # (top, bottom) used as given
    assert screen_geometry_commands(None, None, (1260, 1305)) == [
        "screen_distance = 1260 1305"
    ]


def test_screen_geometry_commands_centre_without_height():
    """Without the height, the centre distance is used for top and bottom."""
    assert screen_geometry_commands(None, None, 600) == ["screen_distance = 600 600"]


@pytest.mark.parametrize(
    ("width", "height", "distance", "match"),
    [
        (530, None, None, "both"),
        (None, 300, None, "both"),
        (-530, 300, None, "positive"),
        (530, 0, None, "positive"),
        (530, 300, "600", "positive"),
        (530, 300, (600,), "top, bottom"),
        (530, 300, (600, -1), "positive"),
        (True, 300, None, "positive"),
    ],
)
def test_screen_geometry_commands_invalid(width, height, distance, match):
    """Test invalid geometry."""
    with pytest.raises(ValueError, match=match):
        screen_geometry_commands(width, height, distance)


def test_screen_geometry_message():
    """Test the EDF message."""
    assert screen_geometry_message(1920, 1080, None, None, None) == (
        "SCREEN_GEOMETRY RES_PX=1920x1080"
    )
    assert screen_geometry_message(2560, 1440, 597.6, 336.2, 650) == (
        "SCREEN_GEOMETRY RES_PX=2560x1440 SIZE_MM=597.6x336.2 DISTANCE_MM=650"
    )
    assert screen_geometry_message(1920, 1080, 530, 300, (1260, 1305)) == (
        "SCREEN_GEOMETRY RES_PX=1920x1080 SIZE_MM=530x300 "
        "DISTANCE_MM_TOP_BOTTOM=1260,1305"
    )
