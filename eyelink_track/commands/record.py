"""eyetrack_record: record eye movements during a task run, started by the trigger."""

from __future__ import annotations

import os
import signal
import sys
from pathlib import Path

import click

from ._rig import rig_option


def _list_keyboards(ctx, param, value):  # noqa: ARG001
    if not value or ctx.resilient_parsing:
        return
    from ..utils.keyboard import list_keyboards

    try:
        keyboards = list_keyboards()
    except RuntimeError as error:
        raise click.ClickException(str(error)) from None
    if not keyboards:
        click.echo(
            "No readable keyboard. Add your user to the 'input' group, then log out "
            "and back in: sudo usermod -aG input $USER"
        )
    for path, name in keyboards:
        click.echo(f"{path}\t{name}")
    ctx.exit()


_STOP_SIGNALS = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)


def _stop_on_signals() -> None:
    """Stop the recording (and save it) on SIGINT, SIGTERM or SIGHUP.

    The handlers are installed explicitly, so that they also work when the program is
    started in the background by a script, where SIGINT is ignored by default.
    """

    def handler(signum, frame):  # noqa: ARG001
        for sig in _STOP_SIGNALS:  # one stop is enough: let the EDF be saved
            signal.signal(sig, signal.SIG_IGN)
        if signum == signal.SIGHUP and sys.stdout.isatty():
            # the terminal was closed: nowhere to print anymore
            sys.stdout = sys.stderr = open(os.devnull, "w")  # noqa: SIM115
        raise KeyboardInterrupt

    for sig in _STOP_SIGNALS:
        signal.signal(sig, handler)
    # printing from the background must not suspend the program
    signal.signal(signal.SIGTTOU, signal.SIG_IGN)


@click.command(name="record")
@rig_option
@click.option("--subject", required=True, help="Subject label, e.g. 01 (or sub-01).")
@click.option("--session", required=True, help="Session label, e.g. 1 (or ses-1).")
@click.option("--run", "run_index", required=True, help="Run index, e.g. 1 (or run-1).")
@click.option(
    "--task",
    required=True,
    help="BIDS task label of the run, e.g. nback (or task-nback).",
)
@click.option(
    "--screen",
    type=int,
    default=0,
    show_default=True,
    help="ID of the screen used by the task (to read its resolution).",
)
@click.option(
    "--resolution",
    metavar="WxH",
    help="Resolution of the task screen, e.g. 1920x1080 (default: read from --screen).",
)
@click.option(
    "--directory",
    help="Directory where the EDF file is saved (default: current directory).",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    default=None,
)
@click.option(
    "--mock",
    help=(
        "Simulate the EyeLink (no Host): messages written to <name>_mock.asc instead "
        "of the EDF. Implies --timing-log."
    ),
    is_flag=True,
)
@click.option(
    "--timing-log",
    help="Write <name>_timing.tsv (recording start, trigger) and print a summary.",
    is_flag=True,
)
@click.option(
    "--list-keyboards",
    help="List the keyboards the program can read (e.g. the trigger box) and exit.",
    is_flag=True,
    expose_value=False,
    is_eager=True,
    callback=_list_keyboards,
)
@click.option(
    "--run-simultaneous",
    help=(
        "Run alongside another program (e.g. started with & from the same shell): "
        "the terminal is not read, and the recording stops and is saved on a signal: "
        "kill <pid>, kill -INT <pid> (Ctrl+C) or closing the terminal. Prints "
        "'Recording. Waiting for the trigger' once ready."
    ),
    is_flag=True,
)
def run(
    subject: str,
    session: str,
    run_index: str,
    task: str,
    screen: int,
    resolution: str | None,
    directory: Path | None,
    mock: bool,
    timing_log: bool,
    run_simultaneous: bool,
) -> None:
    """Record eye movements during a task run, with the current calibration.

    Start this before the task: it starts recording, then waits for the trigger key
    (START_KEY in config.py), read directly from the keyboard devices so that the
    task can keep the focus. The trigger is written to the EDF as t=0. Press ENTER
    here to stop (with --run-simultaneous: send a signal instead); the file is saved
    as sub-<subject>_ses-<session>_task-<task>_run-<run>_eyetrack.edf.
    """
    if run_simultaneous:
        _stop_on_signals()
    from ..config import EDF_SUFFIX, EDF_TEMP_DIGITS, RECORD_KEYBOARD, START_KEY
    from ..utils.bids import make_edf_fname, make_temp_edf_name
    from ..utils.screen import detect_resolution, parse_resolution

    try:
        final_fname = make_edf_fname(
            subject, session, run_index, task=task, suffix=EDF_SUFFIX
        )
        size = (
            detect_resolution(screen)
            if resolution is None
            else parse_resolution(resolution)
        )
    except ValueError as error:
        raise click.BadParameter(str(error)) from None
    directory = Path.cwd() if directory is None else directory
    directory.mkdir(parents=True, exist_ok=True)
    stem = final_fname.removesuffix(".edf")
    if mock:
        stem += "_mock"
        final_fname = f"{stem}.asc"
    timing_fname = f"{stem}_timing.tsv"
    outputs = [directory / final_fname]
    if mock or timing_log:
        outputs.append(directory / timing_fname)
    for output in outputs:
        if output.exists():
            if not mock:
                raise click.ClickException(f"{output} already exists.")
            output.unlink()  # mock outputs are throwaway

    # Open the keyboards first: fail before touching the tracker if not readable
    from ..utils.keyboard import GlobalKeyboard

    try:
        keyboard = GlobalKeyboard([START_KEY], device=RECORD_KEYBOARD)
    except (RuntimeError, ValueError) as error:
        raise click.ClickException(str(error)) from None

    temp_fname = make_temp_edf_name(directory, EDF_TEMP_DIGITS)
    click.echo(
        f"Recording {final_fname} (EyeLink Host file: {temp_fname}.EDF) in "
        f"{directory.resolve()}, screen {size[0]}x{size[1]}"
    )

    from ..eye_link.mock import MockTracker, TimingLog, summarize
    from ..eye_link.recorder import EyelinkRecorder

    timing = TimingLog() if (mock or timing_log) else None
    try:
        tracker = None
        if mock:
            import pylink

            tracker = MockTracker(pylink.EyeLink(None), None, timing)
        recorder = EyelinkRecorder(
            pname=directory,
            fname=temp_fname,
            resolution=size,
            final_fname=final_fname,
            timing=timing,
            tracker=tracker,
            **(dict(host_ip=None) if mock else dict()),
        )
    except BaseException:
        keyboard.close()
        raise
    triggered = False
    try:
        recorder.start()
        stop_hint = (
            f"stop with: kill {os.getpid()}" if run_simultaneous else "Ctrl+C here"
        )
        click.echo(
            f"Recording. Waiting for the trigger key '{START_KEY}'... ({stop_hint})"
        )
        recorder.wait_for_trigger(keyboard)
        triggered = True
        keyboard.close()  # later triggers (e.g. one per volume) are not needed
        if run_simultaneous:
            click.echo(
                f"Trigger received (t=0). Recording until stopped ({stop_hint})."
            )
            while True:
                signal.pause()  # the stop signal raises KeyboardInterrupt
        input(">>> Trigger received (t=0). Press ENTER here to stop the recording.")
    except (KeyboardInterrupt, EOFError):
        click.echo("\nStopping the recording.")
    finally:
        keyboard.close()
        path = recorder.stop()
    click.echo(f"Saved {path}")
    if not triggered:
        click.echo("WARNING: no trigger was received during this recording.")
    if timing is not None:
        timing.write(directory / timing_fname)
        click.echo("\n".join(summarize(timing)))
        click.echo(f"Timing log: {directory / timing_fname}")
    if mock:
        from ..utils.asc import read_messages

        click.echo(f"\nMessages in {path.name}:")
        for t, text in read_messages(path):
            click.echo(f"  {t:12.3f}  {text}")
