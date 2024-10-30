from __future__ import annotations

import click
from qtpy.QtWidgets import QApplication

from .._gui import GUI


@click.command(name="sys-info")
@click.option(
    "--mock",
    help="Use a mock eye-tracker.",
    is_flag=True,
)
def run(mock: bool) -> None:
    """Run the eyelink-track GUI."""
    app = QApplication([])
    kwargs = dict(host_ip=None) if mock else dict()
    window = GUI(**kwargs)  # noqa: F841
    app.exec()
