"""Check the timing messages of an EDF file converted with edf2asc."""

from __future__ import annotations

import re
import statistics
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

_MSG = re.compile(r"^MSG\s+(\d+(?:\.\d+)?)\s+(.*?)\s*$")
_T_REL = re.compile(r"\bT_REL_MS=(-?\d+(?:\.\d+)?)")


def read_messages(path: str | Path) -> list[tuple[float, str]]:
    """Read the MSG lines of an edf2asc file as (timestamp in ms, text)."""
    messages = []
    with open(path, encoding="utf-8", errors="replace") as fid:
        for line in fid:
            match = _MSG.match(line)
            if match:
                messages.append((float(match.group(1)), match.group(2)))
    return messages


def check_messages(
    messages: list[tuple[float, str]], tolerance: float = 3.0
) -> tuple[list[str], bool]:
    """Compare T_REL_MS with the message timestamps relative to START_TRIGGER.

    T_REL_MS is measured on the stimulus PC clock; the message timestamp is set by
    the EyeLink Host when the message arrives. Their difference is the message delay
    relative to the START_TRIGGER message, plus the 1 ms resolution of the EDF.

    Parameters
    ----------
    messages : list of tuple
        Output of :func:`read_messages`.
    tolerance : float
        Maximum accepted spread (max - min) and absolute median, in ms, of the
        difference.

    Returns
    -------
    lines : list of str
        Report.
    ok : bool
        True if a START_TRIGGER and timed messages were found, T_REL_MS increases
        and the differences are within tolerance.
    """
    starts = [(t, text) for t, text in messages if text.startswith("START_TRIGGER")]
    if not starts:
        return ["No START_TRIGGER message found."], False
    t_start, start_text = starts[0]
    lines = [f"START_TRIGGER at {t_start:.3f} ms: {start_text}"]
    if len(starts) > 1:
        lines.append(f"WARNING: {len(starts)} START_TRIGGER messages, using the first.")
    rows = []
    for t, text in messages:
        if t < t_start or text.startswith("START_TRIGGER"):
            continue
        match = _T_REL.search(text)
        if match is not None:
            t_rel = float(match.group(1))
            rows.append((text.split()[0], t_rel, t - t_start, t - t_start - t_rel))
    if not rows:
        lines.append("No message with T_REL_MS after START_TRIGGER.")
        return lines, False
    lines.append(f"{'message':<20}{'T_REL_MS':>12}{'EDF time':>12}{'difference':>12}")
    for name, t_rel, edf_rel, diff in rows:
        lines.append(f"{name:<20}{t_rel:>12.3f}{edf_rel:>12.3f}{diff:>12.3f}")
    diffs = [row[3] for row in rows]
    spread = max(diffs) - min(diffs)
    median = statistics.median(diffs)
    lines.append(
        f"difference (ms): min {min(diffs):.3f}, median {median:.3f}, "
        f"max {max(diffs):.3f}, spread {spread:.3f}"
    )
    ok = spread <= tolerance and abs(median) <= tolerance
    t_rels = [row[1] for row in rows]
    if any(b < a for a, b in zip(t_rels, t_rels[1:], strict=False)):
        lines.append("WARNING: T_REL_MS is not increasing.")
        ok = False
    lines.append(
        "OK" if ok else f"CHECK: differences exceed the tolerance of {tolerance} ms."
    )
    return lines, ok
