[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Imports: isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336)](https://pycqa.github.io/isort/)
[![codecov](https://codecov.io/gh/fcbg-platforms/eyelink-track/graph/badge.svg?token=wqiJ5XFgb9)](https://codecov.io/gh/fcbg-platforms/eyelink-track)
[![tests](https://github.com/fcbg-platforms/eyelink-track/actions/workflows/pytest.yml/badge.svg?branch=main)](https://github.com/fcbg-platforms/eyelink-track/actions/workflows/pytest.yml)

# EyeLink - Track

Standalone program to calibrate an EyeLink 1000 Plus system and to start the recording
on the stimulation PC.

## Install instruction

If installed with [uv](https://docs.astral.sh/uv/), psychopy, wxPython and pylink will
correctly get fetched.

```
uv pip install git+https://github.com/fcbg-platforms/eyelink-track
```

## Requirements

Requires python 3.10 and the `pylink` library.

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
