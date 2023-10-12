[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Imports: isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336)](https://pycqa.github.io/isort/)
[![codecov](https://codecov.io/gh/fcbg-hnp-meeg/eyelink-track/graph/badge.svg?token=wqiJ5XFgb9)](https://codecov.io/gh/fcbg-hnp-meeg/eyelink-track)
[![tests](https://github.com/fcbg-hnp-meeg/eyelink-track/actions/workflows/pytest.yml/badge.svg?branch=main)](https://github.com/fcbg-hnp-meeg/eyelink-track/actions/workflows/pytest.yml)

# EyeLink - Track

Standalone program to calibrate an EyeLink 1000 Plus system and to start the recording
on the stimulation PC.

## Requirements

Requires python 3.9 or above and the `pylink` library.

```
python -m pip install --index-url=https://pypi.sr-support.com sr-research-pylink
```

On Linux, PsychoPy requires:
- wxPython: https://extras.wxpython.org/wxPython4/extras/linux/gtk3/
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
