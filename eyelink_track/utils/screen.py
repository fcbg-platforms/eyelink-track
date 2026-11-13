"""Physical screen geometry sent to the EyeLink."""

from __future__ import annotations

import math

from .logs import logger


def _positive(value, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"{name} must be a positive number of mm, got {value!r}.")
    return float(value)


def screen_geometry_commands(
    width_mm: float | None,
    height_mm: float | None,
    distance_mm: float | tuple[float, float] | None,
) -> list[str]:
    """Build the EyeLink commands describing the screen and the viewing distance.

    Parameters
    ----------
    width_mm, height_mm : float | None
        Size of the visible display area, in mm. Both or neither.
    distance_mm : float | tuple of float | None
        Eye to screen centre, in mm, or (eye to top, eye to bottom) of the display
        area, as EyeLink expects. A centre distance is converted assuming the eye is
        level with the screen centre.

    Returns
    -------
    commands : list of str
        ``screen_phys_coords`` (left, top, right, bottom in mm from the screen
        centre) and/or ``screen_distance`` (eye to top and bottom, in mm). Empty if
        nothing is set, in which case the Host keeps its PHYSICAL.INI values.
    """
    if (width_mm is None) != (height_mm is None):
        raise ValueError("Set both SCREEN_WIDTH_MM and SCREEN_HEIGHT_MM, or neither.")
    commands = []
    if width_mm is not None:
        half_w = _positive(width_mm, "SCREEN_WIDTH_MM") / 2
        half_h = _positive(height_mm, "SCREEN_HEIGHT_MM") / 2
        commands.append(
            f"screen_phys_coords = {-half_w:.1f}, {half_h:.1f}, {half_w:.1f}, "
            f"{-half_h:.1f}"
        )
    if distance_mm is not None:
        if isinstance(distance_mm, (tuple, list)):
            if len(distance_mm) != 2:
                raise ValueError(
                    "SCREEN_DISTANCE_MM must be a number or (top, bottom), got "
                    f"{distance_mm!r}."
                )
            top = _positive(distance_mm[0], "SCREEN_DISTANCE_MM (top)")
            bottom = _positive(distance_mm[1], "SCREEN_DISTANCE_MM (bottom)")
        else:
            centre = _positive(distance_mm, "SCREEN_DISTANCE_MM")
            if height_mm is None:
                logger.warning(
                    "SCREEN_HEIGHT_MM is not set: the eye-to-centre distance is used "
                    "as eye-to-top and eye-to-bottom distance."
                )
                top = bottom = centre
            else:
                top = bottom = math.hypot(centre, height_mm / 2)
        commands.append(f"screen_distance = {top:.0f} {bottom:.0f}")
    return commands


def screen_geometry_message(
    width_px: int,
    height_px: int,
    width_mm: float | None,
    height_mm: float | None,
    distance_mm: float | tuple[float, float] | None,
) -> str:
    """Describe the screen geometry in one EDF message."""
    parts = [f"SCREEN_GEOMETRY RES_PX={width_px}x{height_px}"]
    if width_mm is not None and height_mm is not None:
        parts.append(f"SIZE_MM={width_mm:g}x{height_mm:g}")
    if isinstance(distance_mm, (tuple, list)):
        parts.append(f"DISTANCE_MM_TOP_BOTTOM={distance_mm[0]:g},{distance_mm[1]:g}")
    elif distance_mm is not None:
        parts.append(f"DISTANCE_MM={distance_mm:g}")
    return " ".join(parts)