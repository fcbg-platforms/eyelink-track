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
2. The tracker setup opens (C: calibrate, V: validate, O: start recording).
3. The recording runs until ENTER is pressed in the terminal.
4. The EDF file, recorded on the EyeLink Host under a random 6-digit name, is
   downloaded and renamed to `sub-01_ses-1[_task-rest]_run-1_eyetrack.edf` in
   `--directory` (default: current directory). Existing files are never overwritten.

Without these options, the GUI opens. `--photodiode` also works with
`eyelink_track gui` and `eyelink_track track`.

The TTL must arrive on a status pin of `LPT_ADDRESS` (10, 11, 12, 13 or 15; ground
on 18-25), since the data pins send the calibration triggers. The calibration starts
on the edge into the active level (`START_TTL_ACTIVE_HIGH`), so a pin resting at that
level does not start it. Set `START_TTL_PIN = None` to use the key only.

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
  trigger, photodiode flash, target onsets/offsets and LPT writes on one clock, and
  prints a summary. Also usable on real runs.

To check the timing messages of a real recording, convert it with `edf2asc` (EyeLink
Developers Kit) and run `eyelink_track check-asc <file>.asc`: it compares `T_REL_MS`,
measured on the stimulus PC, with the EDF timestamps relative to `START_TRIGGER`.

The actual photodiode onset relative to the LPT codes can only be measured with the
photodiode and the codes recorded on the same device (EEG/MEG amplifier, scope).
