"""eyetrack_calibration: calibrate and record, without the GUI for a known run."""

from __future__ import annotations

from pathlib import Path

import click


@click.command(name="calibration")
@click.option("--subject", help="Subject label, e.g. 01 (or sub-01).")
@click.option("--session", help="Session label, e.g. 1 (or ses-1).")
@click.option("--run", "run_index", help="Run index, e.g. 1 (or run-1).")
@click.option("--task", help="Optional BIDS task label added to the file name.")
@click.option(
    "--photodiode",
    help="Draw a photodiode patch with each calibration target.",
    is_flag=True,
)
@click.option(
    "--screen", help="ID of the screen to use.", type=int, default=0, show_default=True
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
        "Simulate the EyeLink: 9-point calibration without Host, messages written "
        "to <name>_mock.asc instead of the EDF. Implies --timing-log."
    ),
    is_flag=True,
)
@click.option(
    "--no-lpt",
    help="Simulate the parallel port, with data pin 2 looped back to the TTL input.",
    is_flag=True,
)
@click.option(
    "--loopback",
    type=click.FloatRange(min=0),
    metavar="SECONDS",
    help=(
        "Send the start TTL on data pin 2 after SECONDS. On a real port, wire data "
        "pin 2 to START_TTL_PIN."
    ),
)
@click.option(
    "--timing-log",
    help="Write <name>_timing.tsv (trigger, flips, LPT writes) and print a summary.",
    is_flag=True,
)
def run(
    subject: str | None,
    session: str | None,
    run_index: str | None,
    task: str | None,
    photodiode: bool,
    screen: int,
    directory: Path | None,
    mock: bool,
    no_lpt: bool,
    loopback: float | None,
    timing_log: bool,
) -> None:
    """Calibrate the EyeLink and record.

    With --subject, --session and --run, the GUI is skipped: the program waits for
    the start key or a TTL (see config.py), opens the tracker setup, records, and
    saves sub-<subject>_ses-<session>[_task-<task>]_run-<run>_eyetrack.edf.
    Without them, the GUI opens.
    """
    entities = (subject, session, run_index)
    if all(entity is None for entity in entities):
        headless_only = dict(
            task=task,
            mock=mock,
            no_lpt=no_lpt,
            loopback=loopback,
            timing_log=timing_log,
        )
        used = [
            name.replace("_", "-")
            for name, value in headless_only.items()
            if value is not None and value is not False
        ]
        if used:
            raise click.UsageError(
                f"--{used[0]} requires --subject, --session and --run."
            )
        from .gui import launch_gui

        launch_gui(photodiode=photodiode)
        return
    if any(entity is None for entity in entities):
        raise click.UsageError(
            "--subject, --session and --run must be given together "
            "(or none of them, to open the GUI)."
        )

    from ..config import EDF_SUFFIX, EDF_TEMP_DIGITS, START_TTL_PIN
    from ..utils.bids import make_edf_fname, make_temp_edf_name

    if loopback is not None and START_TTL_PIN is None:
        raise click.UsageError("--loopback requires START_TTL_PIN in config.py.")
    try:
        final_fname = make_edf_fname(
            subject, session, run_index, task=task, suffix=EDF_SUFFIX
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
    temp_fname = make_temp_edf_name(directory, EDF_TEMP_DIGITS)
    click.echo(
        f"Recording {final_fname} (EyeLink Host file: {temp_fname}.EDF) "
        f"in {directory.resolve()}"
    )

    from ..eye_link import Eyelink
    from ..eye_link.mock import (
        MockLPT,
        TimingLog,
        install_mock_tracker,
        schedule_loopback,
        summarize,
    )

    timing = TimingLog() if (mock or timing_log) else None
    if no_lpt:
        click.echo("Parallel port simulated: no trigger leaves this computer.")
    eye_link = Eyelink(
        pname=directory,
        fname=temp_fname,
        screen=screen,
        photodiode=photodiode,
        final_fname=final_fname,
        trigger=MockLPT() if no_lpt else None,
        timing=timing,
        **(dict(host_ip=None) if mock else dict()),
    )
    if mock:
        install_mock_tracker(eye_link, timing)
    timer = None if loopback is None else schedule_loopback(eye_link, loopback, timing)
    try:
        started = eye_link.calibrate(wait_for_trigger=True)
    finally:
        if timer is not None:
            timer.cancel()
    if started:
        eye_link.win.close()
        eye_link.start()
        try:
            input(">>> Press ENTER to stop the recording.")
        except (KeyboardInterrupt, EOFError):
            click.echo("\nStopping the recording.")
        path = eye_link.stop()
        click.echo(f"Saved {path}")
    else:
        eye_link.close()
        click.echo("Aborted before the calibration. Nothing was recorded.")
    if timing is not None:
        timing.write(directory / timing_fname)
        click.echo("\n".join(summarize(timing)))
        click.echo(f"Timing log: {directory / timing_fname}")
    if mock and started:
        from ..utils.asc import check_messages, read_messages

        click.echo(f"\nMessage check of {path.name} (as for a real EDF via edf2asc):")
        click.echo("\n".join(check_messages(read_messages(path))[0]))
