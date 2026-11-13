from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path

import pylink
from psychopy import logging
from psychopy.event import clearEvents, getKeys, waitKeys
from psychopy.visual import TextStim, Window

from ..config import (
    CAL_TRIGGER_MAP,
    FOREGROUND_COLOR,
    HOST_IP,
    LPT_ADDRESS,
    PHOTODIODE_COLOR,
    PHOTODIODE_CORNER,
    PHOTODIODE_SIZE,
    PHOTODIODE_FRAMES,
    SCREEN_KWARGS,
    START_KEY,
    START_TTL_ACTIVE_HIGH,
    START_TTL_PIN,
    START_SETUP_KEYS,
)
from ..utils._checks import check_type, ensure_int, ensure_path
from ..utils.logs import logger
from ..utils.start_trigger import wait_for_start
from .EyeLinkCoreGraphicsPsychoPy import EyeLinkCoreGraphicsPsychoPy

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
    photodiode : bool
        If True, a photodiode patch is drawn with each calibration target.
    final_fname : str | None
        If provided, the downloaded EDF file is renamed to this file name (in
        ``pname``) once the recording is stopped. Used to work around the 8-character
        limit of the EyeLink Host.
    trigger : object | None
        Object with a ``signal(value)`` method sending the calibration triggers. If
        None, the parallel port ``LPT_ADDRESS`` is opened.
    timing : callable | None
        Callable ``(event, t, **fields)`` receiving the display, trigger and start
        times (``time.perf_counter``), e.g. a :class:`~.mock.TimingLog`.
    """

    def __init__(
        self,
        pname: str | Path = "./",
        fname: str = "TEST",
        host_ip: str | None = HOST_IP,
        screen: int | None = None,
        resolution: tuple[int, int] | None = None,
        photodiode: bool = False,
        final_fname: str | None = None,
        trigger=None,
        timing=None,
    ) -> None:
        pname = ensure_path(pname, must_exist=False)
        if not pname.exists():
            os.makedirs(pname)
        self.edf_pname = pname
        check_type(photodiode, (bool,), "photodiode")
        check_type(final_fname, (str, None), "final_fname")
        self.final_edf = None if final_fname is None else pname / final_fname
        if self.final_edf is not None and self.final_edf.exists():
            raise FileExistsError(f"{self.final_edf} already exists.")
        self._timing = timing
        self.t0 = None  # start trigger time (time.perf_counter), once received
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
        self.genv.setCalibrationTriggers(
            mapping=CAL_TRIGGER_MAP,
            trigger_port=LPT_ADDRESS,
            trigger=trigger,
        )
        self.genv.setTimingLog(timing)
        if photodiode:
            self.genv.setPhotodiode(
                size=PHOTODIODE_SIZE,
                corner=PHOTODIODE_CORNER,
                color=PHOTODIODE_COLOR,
                frames=PHOTODIODE_FRAMES,
            )

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

    def calibrate(self, wait_for_trigger: bool = False) -> bool:
        """Run the calibration.

        Parameters
        ----------
        wait_for_trigger : bool
            If True, the tracker setup starts on the start key or on a TTL (see
            START_KEY and START_TTL_PIN in config.py) instead of on any key.

        Returns
        -------
        started : bool
            False if the wait for the start trigger was aborted with Escape.
        """
        self.win.winHandle.activate()
        if wait_for_trigger:
            self.show_msg("Waiting for the start trigger...", wait_for_keypress=False)
            if self.wait_for_trigger() is None:
                return False
            self.clear_screen()
            self.genv.pressKeysInSetup(START_SETUP_KEYS) # Click to access the setup screen (enter manually normally)
        else:
            # Show the task instructions
            task_msg = "\nPress ENTER twice to display tracker menu."
            self.show_msg(task_msg)
        try:
            self.el_tracker.doTrackerSetup()
        except RuntimeError:
            self.el_tracker.exitCalibration()
            self.close()
            raise
        return True

    def wait_for_trigger(
        self,
        key: str = START_KEY,
        ttl_pin: int | None = START_TTL_PIN,
        active_high: bool = START_TTL_ACTIVE_HIGH,
    ) -> str | None:
        """Wait for the start key or a TTL on the LPT port, whichever comes first.

        Parameters
        ----------
        key : str
            PsychoPy name of the start key.
        ttl_pin : int | None
            Status pin of the LPT port receiving the TTL. None to only use the key.
        active_high : bool
            If True, a low to high edge on the pin starts the calibration.

        Returns
        -------
        source : str | None
            ``"key"`` or ``"ttl"``, or None if aborted with Escape.
        """
        read_pin = None
        if ttl_pin is not None:
            ttl_pin = ensure_int(ttl_pin, "ttl_pin")
            read_pin = self.genv.getInputPinReader(ttl_pin)
        logger.info(
            "Waiting for the start key '%s'%s. Press Escape to abort.",
            key,
            "" if ttl_pin is None else f" or a TTL on LPT pin {ttl_pin}",
        )
        clearEvents()
        if self._timing is not None:
            self._timing("WAIT_START", time.perf_counter())
        source = wait_for_start(
            poll_keys=lambda: getKeys(keyList=[key, "escape"]),
            key=key,
            read_pin=read_pin,
            active_level=int(active_high),
        )
        if source is None:
            logger.info("Wait for the start trigger aborted.")
            return None
        # t=0, on the stimulus PC clock. The message is sent right away so that its
        # EDF timestamp (tracker clock) is as close as possible to the trigger.
        t0 = time.perf_counter()
        wallclock = datetime.now().astimezone().isoformat(timespec="microseconds")
        self.el_tracker.sendMessage(
            f"START_TRIGGER {source.upper()} T_REL_MS=0.000 WALLCLOCK={wallclock}"
        )
        self.t0 = t0
        if self._timing is not None:
            self._timing("START_TRIGGER", t0, source=source)
        self.genv.setTimeZero(t0)
        # later triggers (e.g. one per MRI volume) must not reach the tracker setup
        self.genv.setIgnoredKeys([key])
        self.genv.flashPhotodiode()  # logs START_PHOTODIODE
        logger.info("Start trigger received (%s) at %s.", source, wallclock)
        return source

    def start(self):
        """Start recording."""
        self.el_tracker.startRecording(1, 1, 1, 1)
        self.el_tracker.sendMessage("START")

    def stop(self) -> Path:
        """Stop recording, download the EDF file and rename it if requested.

        Returns
        -------
        path : Path
            Path to the local EDF file.
        """
        self.el_tracker.stopRecording()
        self.el_tracker.setOfflineMode()

        # Clear the Host PC screen and wait for 500 ms
        self.el_tracker.sendCommand("clear_screen 0")
        pylink.msecDelay(500)

        # Close the edf data file on the Host
        self.el_tracker.closeDataFile()
        # Download the EDF data file from the Host PC to a local data folder
        # parameters: source_file_on_the_host, destination_file_on_local_drive
        local_edf = self.edf_pname / (self.edf_fname + ".EDF")
        try:
            self.el_tracker.receiveDataFile(self.edf_fname + ".EDF", str(local_edf))
        except RuntimeError:
            raise
        finally:
            self.close()
        return self._rename_edf(local_edf)

    def _rename_edf(self, local_edf: Path) -> Path:
        """Rename the downloaded EDF file to its final name, never overwriting."""
        if self.final_edf is None:
            return local_edf
        if not local_edf.exists():
            logger.error(
                "The EDF file was not downloaded to %s. It is still on the EyeLink "
                "Host as %s.EDF.",
                local_edf,
                self.edf_fname,
            )
            return local_edf
        if self.final_edf.exists():
            logger.error(
                "%s already exists. The recording was kept as %s.",
                self.final_edf,
                local_edf,
            )
            return local_edf
        local_edf.rename(self.final_edf)
        logger.info("Recording saved as %s.", self.final_edf)
        return self.final_edf

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
