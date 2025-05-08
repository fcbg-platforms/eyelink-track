from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pyglet.canvas import Display
from qtpy.QtCore import QRegularExpression, Slot
from qtpy.QtGui import QRegularExpressionValidator
from qtpy.QtWidgets import (
    QAction,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QStatusBar,
    QStyle,
    QToolBar,
    QWidget,
)

from .eye_link import Eyelink
from .utils._checks import check_type


class GUI(QMainWindow):
    """Main window of the GUI.

    Parameters
    ----------
    mock : bool
        If True, uses a mock eye-tracker.
    """

    def __init__(self, mock: bool) -> None:
        check_type(mock, (bool,), "mock")
        self._mock = mock
        super().__init__()
        self.setCentralWidget(CentralWidget())
        # tool bar
        start = QAction(
            self.style().standardIcon(QStyle.SP_MediaPlay),
            "",
            self,
            objectName="start",
        )
        start.triggered.connect(self.start)
        stop = QAction(
            self.style().standardIcon(QStyle.SP_MediaStop),
            "",
            self,
            objectName="stop",
        )
        stop.triggered.connect(self.stop)
        stop.setEnabled(False)
        toolbar = QToolBar()
        toolbar.addAction(start)
        toolbar.addAction(stop)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        # status bar
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("[Not recording]")
        # render
        self.show()

    @Slot()
    def start(self) -> None:
        """Start the EyeTracker calibration and recording."""
        self.findChildren(QAction, name="start")[0].setEnabled(False)
        self.findChildren(QAction, name="stop")[0].setEnabled(True)
        # disable widgets from the central widget
        for widget_type in (QLineEdit, QPushButton, QComboBoxScreen):
            for widget in self.centralWidget().findChildren(widget_type):
                widget.setEnabled(False)
        # retrieve information
        directory = self.centralWidget().findChildren(DirectoryDialog)[0].path
        fname = self.centralWidget().findChildren(LineEditFname)[0].text()
        if len(fname) == 0:
            fname = datetime.now().strftime("%H%M%S")
        screen = self.centralWidget().findChildren(QComboBoxScreen)[0].screen
        resolution = self.centralWidget().findChildren(QComboBoxScreen)[0].resolution
        # start eye-tracker
        kwargs = dict(host_ip=None) if self._mock else dict()
        self.eye_link = Eyelink(
            pname=directory, fname=fname, screen=screen, resolution=resolution, **kwargs
        )
        if not self._mock:
            self.statusBar().showMessage("[Calibrating..]")
            self.eye_link.calibrate()
        self.eye_link.win.close()
        self.statusBar().showMessage("[Recording..]")
        self.eye_link.start()

    @Slot()
    def stop(self) -> None:
        """Stop the EyeTracker calibration and recording."""
        # stop eye-tracker
        self.statusBar().showMessage("[Stopping and transferring file..]")
        self.eye_link.stop()
        self.findChildren(QAction, name="start")[0].setEnabled(True)
        self.findChildren(QAction, name="stop")[0].setEnabled(False)
        # enable widgets from the central widget
        for widget_type in (QLineEdit, QPushButton, QComboBoxScreen):
            for widget in self.centralWidget().findChildren(widget_type):
                widget.setEnabled(True)
        self.statusBar().showMessage("[Not recording]")


class CentralWidget(QWidget):
    """Main widget arranging the settings."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("central_widget")

        # create central widget layout
        layout = QFormLayout(self)
        layout.addRow("Directory:", DirectoryDialog())
        layout.addRow("File name:", LineEditFname())
        layout.addRow("Monitor:", QComboBoxScreen())


class DirectoryDialog(QWidget):
    """QFileDialog and QLineEdit to select the recording directory."""

    def __init__(self) -> None:
        super().__init__()
        self.line = QLineEdit()
        self.line.setText(str(Path.home()))
        self.button = QPushButton()
        self.button.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.button.clicked.connect(self.browse_path)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.line, stretch=1)
        layout.addWidget(self.button)

    @Slot()
    def browse_path(self) -> None:
        """Slot executed when the 'browse' button is pressed."""
        path = QFileDialog.getExistingDirectory(
            self, "Select directory", str(Path.home()), QFileDialog.ShowDirsOnly
        )
        if path:
            self.line.setText(path)

    @property
    def path(self) -> str:
        """Path in the QLineEdit."""
        return self.line.text()


class LineEditFname(QLineEdit):
    """QLineEdit validated for EyeLink file names."""

    def __init__(self):
        super().__init__()
        self.rx = QRegularExpression(r"^[a-zA-Z0-9]{1,8}$")
        self.validator = QRegularExpressionValidator(self.rx)
        self.setValidator(self.validator)


class QComboBoxScreen(QComboBox):
    """QComboBox listing the available screens."""

    def __init__(self):
        super().__init__()
        self.setEditable(False)
        self.screens = Display().get_screens()
        self.addItems(
            [
                f"{k}: (x={screen.x}, y={screen.y}, {screen.width}x{screen.height})"
                for k, screen in enumerate(self.screens)
            ]
        )

    @property
    def screen(self) -> int:
        """ID of the monitor for PsychoPy."""
        return self.currentIndex()

    @property
    def resolution(self) -> tuple[int, int]:
        """Resolution of the monitor."""
        screen = self.screens[self.screen]
        return screen.width, screen.height
