from __future__ import annotations

from importlib.util import find_spec
from typing import TYPE_CHECKING

from .utils.logs import logger

if TYPE_CHECKING:
    import pytest

# The eye_link package imports pylink and psychopy; skip its tests without them.
collect_ignore = []
if find_spec("pylink") is None or find_spec("psychopy") is None:
    collect_ignore.append("eye_link")


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest options."""
    warnings_lines = r"""
    error::
    # psychopy on python 3.11+
    ignore:'locale.getdefaultlocale' is deprecated:DeprecationWarning
    """
    for warning_line in warnings_lines.split("\n"):
        warning_line = warning_line.strip()
        if warning_line and not warning_line.startswith("#"):
            config.addinivalue_line("filterwarnings", warning_line)
    # setup logging
    logger.propagate = True
