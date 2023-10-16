import argparse

from qtpy.QtWidgets import QApplication

from .._gui import GUI


def run():
    """Run the eyelink-track GUI."""
    parser = argparse.ArgumentParser(
        prog=f"{__package__.split('.')[0]}-sys_info", description="gui"
    )
    parser.add_argument(
        "--mock",
        help="use a mock eye-tracker",
        action="store_true",
    )
    args = parser.parse_args()
    app = QApplication([])
    kwargs = dict(host_ip=None) if args.mock else dict()
    window = GUI(**kwargs)  # noqa: F841
    app.exec()
