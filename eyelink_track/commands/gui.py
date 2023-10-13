from qtpy.QtWidgets import QApplication

from .._gui import GUI


def run():
    """Run the eyelink-track GUI."""
    app = QApplication([])
    window = GUI()  # noqa: F841
    app.exec()
