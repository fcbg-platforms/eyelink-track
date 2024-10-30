from __future__ import annotations

import click
from qtpy.QtWidgets import QApplication


@click.command(name="gui")
@click.option(
    "--mock",
    help="Use a mock eye-tracker.",
    is_flag=True,
)
def run(mock: bool) -> None:
    """Run the eyelink-track GUI."""
    from .._gui import GUI

    app = QApplication([])
    kwargs = dict(host_ip=None) if mock else dict()
    window = GUI(**kwargs)  # noqa: F841
    app.exec()
