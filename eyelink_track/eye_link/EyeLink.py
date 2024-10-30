from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pylink
from psychopy import logging
from psychopy.event import waitKeys
from psychopy.visual import TextStim, Window

from ..config import FOREGROUND_COLOR, HOST_IP, SCREEN_KWARGS
from ..utils._checks import check_type, ensure_int, ensure_path
from ..utils.logs import logger
from .EyeLinkCoreGraphicsPsychoPy import EyeLinkCoreGraphicsPsychoPy

if TYPE_CHECKING:
    from pathlib import Path

# set psychopy log level
logging.console.setLevel(logging.CRITICAL)


class Eyelink:
    """Eyelink class which communicates with the Eye-Tracker device from SR Research.

    Parameters
    ----------
    pname : path-like
        Path to the directory where the .EDF file is saved locally.
    fname : str
        Name of the .EDF file saved. The file name should not exceed 8 alphanumerical
        characters (number 0-9, letters and '_' (underscores), and should not include
        the extension '.EDF'.
    host_ip : str | None
        IP Address of the computer hosting the eye-tracking device.
        If None, a dummy eye-tracker is created.
    screen : int | None
        IDx of the screen to use.
    resolution : tuple | None
        Resolution of the screen to set.
    """

    def __init__(
        self,
        pname: str | Path = "./",
        fname: str = "TEST",
        host_ip: str | None = HOST_IP,
        screen: int | None = None,
        resolution: tuple[int, int] | None = None,
    ) -> None:
        pname = ensure_path(pname, must_exist=False)
        if not pname.exists():
            os.makedirs(pname)
        self.edf_pname = pname
        check_type(fname, (str,), "fname")
        if fname.endswith(".EDF"):
            fname = fname.split(".EDF")[0]
        if 8 < len(fname):
            raise ValueError("The fname should not exceed 8 alphanumeric characters.")
        if screen is not None:
            screen = ensure_int(screen, "screen")
            if screen < 0:
                raise ValueError("The screen ID should be a 0-index integer.")
        if resolution is not None:
            check_type(resolution, (tuple,), "resolution")
            if len(resolution) != 2:
                raise ValueError("The resolution should be a tuple of 2 integers.")
            resolution = tuple(ensure_int(res, "resolution") for res in resolution)
        self.edf_fname = fname

        # ----------------------------------------------------------------------
        # Step 1: Connect to the EyeLink Host PC
        try:
            self.el_tracker = pylink.EyeLink(host_ip)
        except RuntimeError:
            self.close()
            raise

        # -------------------------------------------------------------------
        # Step 2: Open an EDF data file on the Host PC
        try:
            self.el_tracker.openDataFile(self.edf_fname + ".EDF")
        except RuntimeError:
            self.close()
            raise

        # -------------------------------------------------------------------
        # Step 3: Configure the tracker
        # Put the tracker in offline mode before we change tracking parameters
        self.el_tracker.setOfflineMode()

        # Get the software version:
        # 1-EyeLink I, 2-EyeLink II, 3/4-EyeLink 1000, 5-EyeLink 1000 Plus,
        # 6-Portable DUO
        eyelink_ver = 0  # set version to 0, in case running in Dummy mode
        if host_ip is not None:
            vstr = self.el_tracker.getTrackerVersionString()
            eyelink_ver = int(vstr.split()[-1].split(".")[0])
            logger.debug("Running experiment on %s, version %d", vstr, eyelink_ver)

        # File and Link data control
        # -> what eye events to save in the EDF file?
        # -> include everything by default
        file_event_flags = "LEFT,RIGHT,FIXATION,SACCADE,BLINK,MESSAGE,BUTTON,INPUT"
        # -> what eye events to make available over the link?
        # -> include everything by default
        link_event_flags = "LEFT,RIGHT,FIXATION,SACCADE,BLINK,BUTTON,FIXUPDATE,INPUT"
        # what sample data to save in the EDF data file and to make available
        # over the link, include the 'HTARGET' flag to save head target sticker
        # data for supported eye trackers.
        if eyelink_ver > 3:
            file_sample_flags = (
                "LEFT,RIGHT,GAZE,HREF,RAW,AREA,HTARGET," + "GAZERES,BUTTON,STATUS,INPUT"
            )
            link_sample_flags = "LEFT,RIGHT,GAZE,GAZERES,AREA,HTARGET,STATUS,INPUT"
        else:
            file_sample_flags = (
                "LEFT,RIGHT,GAZE,HREF,RAW,AREA,GAZERES,BUTTON,STATUS,INPUT"
            )
            link_sample_flags = "LEFT,RIGHT,GAZE,GAZERES,AREA,STATUS,INPUT"

        self.el_tracker.sendCommand(f"file_event_filter = {file_event_flags}")
        self.el_tracker.sendCommand(f"file_sample_data = {file_sample_flags}")
        self.el_tracker.sendCommand(f"link_event_filter = {link_event_flags}")
        self.el_tracker.sendCommand(f"link_sample_data = {link_sample_flags}")

        # Choose a calibration type, H3, HV3, HV5, HV13
        # (HV = horizontal/vertical)
        self.el_tracker.sendCommand("calibration_type = HV9")
        self.el_tracker.sendCommand("button_function 5 'accept_target_fixation'")

        # Step 4: set up a graphics environment for calibration
        SCREEN_KWARGS["screen"] = 0 if screen is None else screen
        SCREEN_KWARGS["size"] = resolution if resolution is not None else (1920, 1080)
        self.win = Window(units="pix", **SCREEN_KWARGS)

        # get the native screen resolution used by PsychoPy
        self.scn_width, self.scn_height = self.win.size

        # Pass the display pixel coordinates (left, top, right, bottom) to the
        # tracker, c.f EyeLink Installation Guide "Customizing Screen Settings"
        el_coords = (
            "screen_pixel_coords = 0 0 " + f"{self.scn_width - 1} {self.scn_height - 1}"
        )
        self.el_tracker.sendCommand(el_coords)

        # Configure a graphics environment (genv) for tracker calibration
        self.genv = EyeLinkCoreGraphicsPsychoPy(self.el_tracker, self.win)
        logger.debug(self.genv)  # version number of the CoreGraphics library

        # Set background and foreground colors for the calibration target
        # in PsychoPy, (-1, -1, -1)=black, (1, 1, 1)=white, (0, 0, 0)=mid-gray
        foreground_color = FOREGROUND_COLOR
        background_color = self.win.color
        self.genv.setCalibrationColors(foreground_color, background_color)
        self.genv.setTargetType("circle")
        self.genv.setTargetSize(24)
        pylink.openGraphicsEx(self.genv)

    def clear_screen(self):
        """Clear up the PsychoPy window."""
        self.win.fillColor = self.genv.getBackgroundColor()
        self.win.flip()

    def show_msg(self, text, wait_for_keypress=True):
        """Show task instructions on screen."""
        msg = TextStim(
            self.win,
            text,
            color=self.genv.getForegroundColor(),
            wrapWidth=self.scn_width / 2,
        )
        self.clear_screen()
        msg.draw()
        self.win.flip()

        # wait indefinitely, terminates upon key-press
        if wait_for_keypress:
            waitKeys()
            self.clear_screen()

    def calibrate(self):
        """Run the calibration."""
        # Show the task instructions
        task_msg = "\nPress ENTER twice to display tracker menu."
        self.win.winHandle.activate()
        self.show_msg(task_msg)
        try:
            self.el_tracker.doTrackerSetup()
        except RuntimeError:
            self.el_tracker.exitCalibration()
            self.close()
            raise

    def start(self):
        """Start recording."""
        self.el_tracker.startRecording(1, 1, 1, 1)
        self.el_tracker.sendMessage("START")

    def stop(self):
        """Stop recording."""
        self.el_tracker.stopRecording()
        self.el_tracker.setOfflineMode()

        # Clear the Host PC screen and wait for 500 ms
        self.el_tracker.sendCommand("clear_screen 0")
        pylink.msecDelay(500)

        # Close the edf data file on the Host
        self.el_tracker.closeDataFile()
        # Download the EDF data file from the Host PC to a local data folder
        # parameters: source_file_on_the_host, destination_file_on_local_drive
        local_edf = str(self.edf_pname / (self.edf_fname + ".EDF"))
        try:
            self.el_tracker.receiveDataFile(self.edf_fname + ".EDF", local_edf)
        except RuntimeError:
            raise
        finally:
            self.close()

    def signal(self, value: str):
        """Send a trigger signal."""
        self.el_tracker.sendMessage(value)

    def close(self):
        """Close in case a RuntimeError was raised."""
        try:
            self.el_tracker.close()
        except Exception:
            pass
        try:
            self.win.flip()  # flush win.callOnFlip() and win.timeOnFlip()
            self.win.close()
        except Exception:
            pass
        pylink.closeGraphics()
