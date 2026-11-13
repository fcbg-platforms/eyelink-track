"""BIDS-style file naming for the EDF recordings."""

from __future__ import annotations

import re
import secrets
from typing import TYPE_CHECKING

from ._checks import check_type, ensure_int

if TYPE_CHECKING:
    from pathlib import Path

_LABEL = re.compile(r"^[a-zA-Z0-9]+$")


def _clean_label(value: str | int, entity: str) -> str:
    """Return a BIDS label, accepting an optional '<entity>-' prefix."""
    check_type(value, (str, "int-like"), entity)
    value = str(value).strip()
    if value.startswith(f"{entity}-"):
        value = value[len(entity) + 1 :]
    if not _LABEL.match(value):
        raise ValueError(
            f"Invalid BIDS label {value!r} for '{entity}': only letters and digits "
            "are allowed (no '-', '_' or spaces)."
        )
    return value


def make_edf_fname(
    subject: str | int,
    session: str | int,
    run: str | int,
    task: str | None = None,
    suffix: str = "eyetrack",
) -> str:
    """Build the BIDS-style name of the final EDF file.

    Parameters
    ----------
    subject : str | int
        Subject label, with or without the ``sub-`` prefix.
    session : str | int
        Session label, with or without the ``ses-`` prefix.
    run : str | int
        Run index (non-negative integer), with or without the ``run-`` prefix.
    task : str | None
        Optional task label, with or without the ``task-`` prefix.
    suffix : str
        Suffix placed before the extension.

    Returns
    -------
    fname : str
        e.g. ``sub-01_ses-1_task-rest_run-1_eyetrack.edf``.
    """
    entities = [
        f"sub-{_clean_label(subject, 'sub')}",
        f"ses-{_clean_label(session, 'ses')}",
    ]
    if task is not None:
        entities.append(f"task-{_clean_label(task, 'task')}")
    run = _clean_label(run, "run")
    if not run.isdigit():
        raise ValueError(f"The run must be a non-negative integer, got {run!r}.")
    entities.append(f"run-{run}")
    check_type(suffix, (str,), "suffix")
    if not _LABEL.match(suffix):
        raise ValueError(f"Invalid suffix {suffix!r}: only letters and digits allowed.")
    return "_".join(entities) + f"_{suffix}.edf"


def make_temp_edf_name(directory: Path, n_digits: int = 6) -> str:
    """Draw a random numeric EDF name (without extension) not yet used in directory.

    The EyeLink Host limits EDF names to 8 alphanumeric characters.
    """
    n_digits = ensure_int(n_digits, "n_digits")
    if not 1 <= n_digits <= 8:
        raise ValueError("n_digits must be between 1 and 8 (EyeLink Host limit).")
    for _ in range(1000):
        name = "".join(secrets.choice("0123456789") for _ in range(n_digits))
        if not (directory / f"{name}.EDF").exists():
            return name
    raise RuntimeError(f"Could not find an unused temporary EDF name in {directory}.")
