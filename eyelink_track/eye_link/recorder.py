"""Record eye movements during a task: no calibration, no window.

The tracker keeps the calibration done beforehand with eyetrack_calibration. The
recorder opens a new EDF file, starts recording, waits for the start trigger key
(read from the keyboard devices, so the task program can keep the focus), marks it
as t=0 and records until stopped.
"""

from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path

import pylink

from ..config import (
    HOST_IP,
    SCREEN_DISTANCE_MM,
    SCREEN_HEIGHT_MM,
    SCREEN_WIDTH_MM,
    START_KEY,
)
from ..utils._checks import check_type, ensure_path
from ..utils.logs import logger
from ..utils.screen import screen_geometry_commands, screen_geometry_message
from ..utils.start_trigger import wait_for_start


def configure_data(el_tracker, host_ip: str | None) -> None:
    """Select the data saved in the EDF and sent over the link (as Eyelink does)."""
    eyelink_ver = 0  # dummy mode
    if host_ip is not None:
        vstr = el_tracker.getTrackerVersionString()
        eyelink_ver = int(vstr.split()[-1].split(".")[0])
        logger.debug("Recording with %s, version %d", vstr, eyelink_ver)
    file_event_flags = "LEFT,RIGHT,FIXATION,SACCADE,BLINK,MESSAGE,BUTTON,INPUT"
    link_event_flags = "LEFT,RIGHT,FIXATION,SACCADE,BLINK,BUTTON,FIXUPDATE,INPUT"
    if eyelink_ver > 3:
        file_sample_flags = (
            "LEFT,RIGHT,GAZE,HREF,RAW,AREA,HTARGET,GAZERES,BUTTON,STATUS,INPUT"
        )
        link_sample_flags = "LEFT,RIGHT,GAZE,GAZERES,AREA,HTARGET,STATUS,INPUT"
    else:
        file_sample_flags = "LEFT,RIGHT,GAZE,HREF,RAW,AREA,GAZERES,BUTTON,STATUS,INPUT"
        link_sample_flags = "LEFT,RIGHT,GAZE,GAZERES,AREA,STATUS,INPUT"
    el_tracker.sendCommand(f"file_event_filter = {file_event_flags}")
    el_tracker.sendCommand(f"file_sample_data = {file_sample_flags}")
    el_tracker.sendCommand(f"link_event_filter = {link_event_flags}")
    el_tracker.sendCommand(f"link_sample_data = {link_sample_flags}")


class EyelinkRecorder:
    """Record with the current calibration, starting the run at a trigger key.

    Parameters
    ----------
    pname : str | Path
        Directory where the EDF file is saved.
    fname : str
        Name of the EDF file on the EyeLink Host (at most 8 characters).
    resolution : tuple of int
        Resolution of the screen used by the task, which must be the one used for
        the calibration.
    host_ip : str | None
        IP of the EyeLink Host. None for a dummy connection.
    final_fname : str | None
        If provided, the downloaded EDF file is renamed to this file name.
    timing : callable | None
        Callable ``(event, t, **fields)`` receiving the start and trigger times.
    tracker : object | None
        Tracker connection to use instead of connecting to ``host_ip``, e.g. a
        :class:`~.mock.MockTracker`.
    """

    def __init__(
        self,
        pname: str | Path,
        fname: str,
        resolution: tuple[int, int],
        host_ip: str | None = HOST_IP,
        final_fname: str | None = None,
        timing=None,
        tracker=None,
    ) -> None:
        pname = ensure_path(pname, must_exist=False)
        os.makedirs(pname, exist_ok=True)
        check_type(fname, (str,), "fname")
        if 8 < len(fname):
            raise ValueError("The fname should not exceed 8 alphanumeric characters.")
        check_type(final_fname, (str, None), "final_fname")
        self.edf_pname = pname
        self.edf_fname = fname
        self.final_edf = None if final_fname is None else pname / final_fname
        if self.final_edf is not None and self.final_edf.exists():
            raise FileExistsError(f"{self.final_edf} already exists.")
        self._timing = timing
        self.t0 = None  # trigger time (time.perf_counter), once received
        width, height = (int(value) for value in resolution)

        self.el_tracker = pylink.EyeLink(host_ip) if tracker is None else tracker
        try:
            self.el_tracker.openDataFile(fname + ".EDF")
            self.el_tracker.setOfflineMode()
            configure_data(self.el_tracker, host_ip)
            # Same screen description as for the calibration; calibration_type is
            # not sent, so the calibration done beforehand is kept.
            self.el_tracker.sendCommand(
                f"screen_pixel_coords = 0 0 {width - 1} {height - 1}"
            )
            for command in screen_geometry_commands(
                SCREEN_WIDTH_MM, SCREEN_HEIGHT_MM, SCREEN_DISTANCE_MM
            ):
                self.el_tracker.sendCommand(command)
            self.el_tracker.sendMessage(f"DISPLAY_COORDS 0 0 {width - 1} {height - 1}")
            self.el_tracker.sendMessage(
                screen_geometry_message(
                    width, height, SCREEN_WIDTH_MM, SCREEN_HEIGHT_MM, SCREEN_DISTANCE_MM
                )
            )
        except RuntimeError:
            self.close()
            raise

    def _log(self, event: str, t: float | None = None, **fields) -> None:
        if self._timing is not None:
            self._timing(event, t, **fields)

    def start(self) -> None:
        """Start recording, before the trigger."""
        error = self.el_tracker.startRecording(1, 1, 1, 1)
        if error:
            raise RuntimeError(
                f"The EyeLink could not start recording (error {error})."
            )
        pylink.pumpDelay(100)  # let the tracker cache the first samples
        self.el_tracker.sendMessage("START")
        self._log("RECORDING_START")
        logger.info("Recording started.")

    def wait_for_trigger(self, keyboard, key: str = START_KEY) -> str:
        """Wait for the trigger key and mark it as t=0 in the EDF.

        Parameters
        ----------
        keyboard : GlobalKeyboard
            Keyboard devices to read the key from.
        key : str
            PsychoPy name of the trigger key.

        Returns
        -------
        source : str
            ``"key"``.
        """
        keyboard.flush()
        self._log("WAIT_START")
        source = wait_for_start(poll_keys=keyboard.poll, key=key, abort_key="")
        t0 = time.perf_counter()
        # time between the key event (kernel timestamp) and its detection here
        delay = (
            0.0
            if keyboard.last_event_time is None
            else max(0.0, (time.time() - keyboard.last_event_time) * 1000)
        )
        wallclock = datetime.now().astimezone().isoformat(timespec="microseconds")
        self.el_tracker.sendMessage(
            f"START_TRIGGER {source.upper()} T_REL_MS=0.000 WALLCLOCK={wallclock} "
            f"DETECT_DELAY_MS={delay:.3f}"
        )
        self.t0 = t0
        self._log(
            "START_TRIGGER",
            t0,
            source=source,
            detect_delay_ms=f"{delay:.3f}",
            wallclock=wallclock,
        )
        logger.info("Trigger received at %s.", wallclock)
        return source

    def stop(self) -> Path:
        """Stop recording, download the EDF file and rename it if requested."""
        if self.t0 is not None:
            elapsed = (time.perf_counter() - self.t0) * 1000
            self.el_tracker.sendMessage(f"RECORDING_END ELAPSED_MS={elapsed:.3f}")
        pylink.pumpDelay(100)  # record a little after the last event
        self.el_tracker.stopRecording()
        self._log("RECORDING_STOP")
        self.el_tracker.setOfflineMode()
        pylink.msecDelay(500)
        self.el_tracker.closeDataFile()
        local_edf = self.edf_pname / (self.edf_fname + ".EDF")
        try:
            self.el_tracker.receiveDataFile(self.edf_fname + ".EDF", str(local_edf))
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

    def close(self) -> None:
        """Close the connection to the tracker."""
        try:
            self.el_tracker.close()
        except Exception:
            pass
