from __future__ import annotations

import click


def launch_gui(mock: bool = False, photodiode: bool = False) -> None:
    """Open the eyelink-track GUI and block until it is closed."""
    from qtpy.QtWidgets import QApplication

    from .._gui import GUI

    app = QApplication([])
    window = GUI(mock, photodiode=photodiode)  # noqa: F841
    app.exec()


@click.command(name="gui")
@click.option(
    "--mock",
    help="Use a mock eye-tracker.",
    is_flag=True,
)
@click.option(
    "--photodiode",
    help="Draw a photodiode patch with each calibration target.",
    is_flag=True,
)
def run(mock: bool, photodiode: bool) -> None:
    """Run the eyelink-track GUI."""
    launch_gui(mock=mock, photodiode=photodiode)
