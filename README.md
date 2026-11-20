[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Imports: isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336)](https://pycqa.github.io/isort/)
[![codecov](https://codecov.io/gh/fcbg-platforms/eyelink-track/graph/badge.svg?token=wqiJ5XFgb9)](https://codecov.io/gh/fcbg-platforms/eyelink-track)
[![tests](https://github.com/fcbg-platforms/eyelink-track/actions/workflows/pytest.yml/badge.svg?branch=main)](https://github.com/fcbg-platforms/eyelink-track/actions/workflows/pytest.yml)

# EyeLink - Track

Standalone program to calibrate an EyeLink 1000 Plus system and to start the recording
on the stimulation PC.

This dev version sends LPT triggers on calibration dots.

## Install instruction

If installed with [uv](https://docs.astral.sh/uv/), psychopy, wxPython and pylink will
correctly get fetched.

```
uv pip install git+https://github.com/fcbg-platforms/eyelink-track@dev_cal_triggers
```

Or:
```
git clone https://github.com/fcbg-platforms/eyelink-track.git
cd eyelink-track
uv venv --python 3.11
source .venv/bin/activate
uv pip install sr-research-pylink==2.2.596.0
uv pip install -e ".[test]"
```

## Requirements

Requires python 3.11 and the `pylink` library.

```
python -m pip install --index-url=https://pypi.sr-support.com sr-research-pylink
```

On Linux, PsychoPy requires:
- APT libraries

```
sudo apt install libusb-1.0-0-dev portaudio19-dev libasound2-dev libsdl2-2.0-0
```

- Elevated user privileges, e.g. via a `psychopy` group

```
sudo groupadd --force psychopy
sudo usermod -a -G psychopy $USER
sudo nano /etc/security/limits.d/99-psychopylimits.conf

    @psychopy   -  nice       -20
    @psychopy   -  rtprio     50
    @psychopy   -  memlock    unlimited
```

c.f. https://www.thegeekdiary.com/understanding-etc-security-limits-conf-file-to-set-ulimit/
for additional information on `ulimit`.

PsychoPy requires wxPython, which can be difficult to compile from source on linux.
Wheels are available here: https://extras.wxpython.org/wxPython4/extras/linux/gtk3/

## Config.py
Set constants in this file: this is where port should be specified, as well as trigger signals.

Screen geometry: set `SCREEN_WIDTH_MM` and `SCREEN_HEIGHT_MM` (visible display
area) and `SCREEN_DISTANCE_MM` (eye to screen centre, or `(top, bottom)` distances).
They are sent to the EyeLink at startup (`screen_phys_coords`, `screen_distance`),
overriding the Host's PHYSICAL.INI for the session, so that saccades, fixations and
velocities are computed in the right degrees of visual angle. They are also written to
the EDF as `SCREEN_GEOMETRY`. Leave them at `None` to keep the Host's settings.

### Rig files

`config.py` holds the defaults. To switch between setups (scanner, MEG, lab), put
the values that differ in a JSON file and pass it with `--rig` to
`eyetrack_calibration` and `eyetrack_record`:

```
eyetrack_calibration --rig rigs/mri.json --subject 01 --session 1 --run 1
eyetrack_record --rig rigs/mri.json --subject 01 --session 1 --run 1 --task nback
```

```json
{
  "_comment": "3T scanner: projector and mirror, fORP trigger box",
  "SCREEN_WIDTH_MM": 400,
  "SCREEN_HEIGHT_MM": 300,
  "SCREEN_DISTANCE_MM": [1260, 1305],
  "START_KEY": "5",
  "RECORD_KEYBOARD": "fORP",
  "SCREEN_KWARGS": {"screen": 1}
}
```

Names are those of `config.py`; only the listed ones change. Keys starting with `_`
are comments. Lists become tuples, and a dict is merged into the `config.py` dict
(for `CAL_TRIGGER_MAP`, keys are written `"row,col"`). The file is checked before
anything starts: unknown names and wrong types are refused. The applied values are
printed at startup.

## Calibration without the GUI

We support a GUI-less calibration step. This calibration allows to open directly the calibration software and will await a start signal to be MRI-compatible. It also supports a photodiode, which will flash when the start key is pressed, and afterwards at every
fixation trigger.

```
eyetrack_calibration --subject 01 --session 1 --run 1 [--task rest] [--photodiode]
# or, from a clone of this repository:
python eyetrack_calibration.py --subject 01 --session 1 --run 1
```

With `--subject`, `--session` and `--run`, the GUI is skipped:

1. The program waits for the start key (`START_KEY`) or a TTL on the parallel port
   (`START_TTL_PIN`), whichever comes first. Escape aborts. This first trigger is
   t=0: it is written to the EDF as
   `START_TRIGGER <KEY|TTL> T_REL_MS=0.000 WALLCLOCK=<ISO date>`, and each
   `CAL_DOT_<n> X=.. Y=..` message gets `T_REL_MS=<ms since t=0>`, measured on the
   stimulus PC clock at the flip showing the target. With `--photodiode`, the patch
   also flashes once at t=0 (`START_PHOTODIODE T_REL_MS=..`). Later triggers, e.g.
   one per MRI volume, are ignored, and the start key is not passed to the setup.
2. The tracker setup opens, and the program presses Enter for you
   (`START_SETUP_KEYS`) so the camera image and menu appear directly
   (C: calibrate, V: validate, O: start recording).
3. The recording runs until ENTER is pressed in the terminal.
4. The EDF file, recorded on the EyeLink Host under a random 6-digit name, is
   downloaded and renamed to `sub-01_ses-1[_task-rest]_run-1_eyetrack.edf` in
   `--directory` (default: current directory). Existing files are never overwritten.

Without these options, the GUI opens. `--photodiode` also works with
`eyelink_track gui` and `eyelink_track track`: the patch (`PHOTODIODE_CORNER`,
`PHOTODIODE_SIZE`) is pulsed for `PHOTODIODE_FRAMES` frames (default 2) at the start
trigger and at each calibration/validation target, in the same flip as the target and
its LPT code. The target stays on screen after the pulse.

The TTL must arrive on a status pin of `LPT_ADDRESS` (10, 11, 12, 13 or 15; ground
on 18-25), since the data pins send the calibration triggers. The calibration starts
on the edge into the active level (`START_TTL_ACTIVE_HIGH`), so a pin resting at that
level does not start it. Set `START_TTL_PIN = None` to use the key only.

## Recording a task run

After the calibration, record each run of the task with:

```
eyetrack_record --subject 01 --session 1 --run 1 --task nback
```

1. Start `eyetrack_record` first, then the task. The recorder opens no window: it
   starts recording right away, with the calibration kept by the tracker, and waits
   for `START_KEY`.
2. The scanner trigger is read directly from the keyboard devices, so the task keeps
   the focus and still receives the key. The first trigger is written to the EDF as
   `START_TRIGGER KEY T_REL_MS=0.000 WALLCLOCK=<ISO date> DETECT_DELAY_MS=<ms>`,
   inside the recording. Later triggers are ignored.
3. Press ENTER in the recorder's terminal at the end of the run (Ctrl+C before the
   trigger also stops and saves). The file is saved as
   `sub-01_ses-1_task-nback_run-1_eyetrack.edf`; existing files are never overwritten.

Requirements and tips:

- Reading the keyboard devices requires the `evdev` package (installed with the
  package) and your user in the `input` group:
  `sudo usermod -aG input $USER`, then log out and back in.
- `eyetrack_record --list-keyboards` lists the readable keyboards. Set
  `RECORD_KEYBOARD` in `config.py` to the trigger box (part of its name) so that the
  experimenter's keyboard cannot start the run.
- The task must use the same screen and resolution as the calibration. The
  resolution is read from `--screen` (or set with `--resolution 1920x1080`).
- `--mock` and `--timing-log` work as for the calibration.

Running alongside another program (e.g. the task) from one shell line:
`--run-simultaneous` makes the recorder ignore the terminal and stop on a signal
instead: `kill <pid>`, `kill -INT <pid>` (Ctrl+C) or closing the terminal all stop the
recording and save the EDF. It prints `Recording. Waiting for the trigger` once
ready:

```bash
eyetrack_record --run-simultaneous --rig mri.json --subject 01 --session 1 --run 1 --task nback > rec.log 2>&1 & REC=$!; until grep -q "Waiting for the trigger" rec.log || ! kill -0 $REC 2>/dev/null; do sleep 0.2; done; kill -0 $REC 2>/dev/null && python nback.py --subject 01 --run 1; kill $REC; wait $REC; cat rec.log
```

## Testing without the eye-tracker

```
eyetrack_calibration --subject test --session 1 --run 1 --mock --no-lpt --loopback 3 --photodiode
```

- `--mock`: no EyeLink Host needed. A 9-point calibration (random order, 1 s per
  target) runs through the real display and trigger code, and the messages are
  written to `sub-test_ses-1_run-1_eyetrack_mock.asc`, in the format of `edf2asc`
  (no gaze samples). Mock outputs are overwritten. Escape stops the calibration.
- `--no-lpt`: no parallel port needed. The codes are logged instead of sent, and data
  pin 2 is looped back to the TTL input.
- `--loopback SECONDS`: sends the start TTL (code 1, data pin 2) after SECONDS. On a
  real port, wire data pin 2 to `START_TTL_PIN` to test the TTL input end to end.
  Without `--loopback`, start with `START_KEY`.
- `--timing-log` (implied by `--mock`): writes `<name>_timing.tsv` with the start
  trigger, photodiode pulses, target onsets/offsets and LPT writes on one clock, and
  prints a summary. Also usable on real runs.

To check the timing messages of a real recording, convert it with `edf2asc` (EyeLink
Developers Kit) and run `eyelink_track check-asc <file>.asc`: it compares `T_REL_MS`,
measured on the stimulus PC, with the EDF timestamps relative to `START_TRIGGER`.

The actual photodiode onset relative to the LPT codes can only be measured with the
photodiode and the codes recorded on the same device (EEG/MEG amplifier, scope).

### Testing the recording next to a task

`tools/dummy_task.py` stands in for a real task: it opens a window, waits for the
trigger key, counts every key it receives for `--duration` seconds, and quits on
Escape. With `--mock`, no eye-tracker is needed (the keyboard devices are still read,
see the requirements above):

```bash
eyetrack_record --run-simultaneous --mock --subject test --session 1 --run 1 --task dummy > rec.log 2>&1 & REC=$!; until grep -q "Waiting for the trigger" rec.log || ! kill -0 $REC 2>/dev/null; do sleep 0.2; done; kill -0 $REC 2>/dev/null && python tools/dummy_task.py --duration 20 --windowed; kill $REC; wait $REC; cat rec.log
```

Press `t` (and other keys) in the task window. Check that the task counts every key,
that `TASK trigger received at` and the recorder's `Start trigger ... at` show the
same time, and that the recording covers the whole task (`recording started at` /
`recording stopped at`). Run it again pressing Escape early: the task quits and the
recording is still saved.
