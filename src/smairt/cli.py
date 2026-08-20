# See docs/ARCHITECTURE.md for the full tour of how a command flows from here
# down into the shared modules (project.py, units.py, check.py, ...).
"""``smairt`` — the command-line entry point every researcher and harness actually types.

This is the thin top layer: each function below is one ``smairt`` subcommand
(``new``, ``adopt``, ``check``, ``status``, ``connect``, ``unit new``,
``index``). None of them contain real logic — each one just parses its
options (Typer, the library imported below, turns each function's arguments
into CLI flags automatically), calls into the matching module
(:mod:`smairt.project`, :mod:`smairt.units`, :mod:`smairt.check`, etc.) to do
the actual work, and prints the result.

Note for readers: a command function's docstring becomes its ``--help`` text
(Typer reads it directly), so those docstrings are part of SMAIRT's public,
user-facing behavior — unlike everywhere else in this codebase, they are not
free to reword.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import NoReturn

import typer

from smairt import __version__
from smairt import adopt as adopt_module
from smairt import check as check_module
from smairt import connect as connect_module
from smairt import data as data_module
from smairt import index as index_module
from smairt import project as project_module
from smairt import status as status_module
from smairt import units as units_module
from smairt.fsutil import PathExistsError
from smairt.project import Harness
from smairt.text import slugify

app = typer.Typer(
    no_args_is_help=True,
    invoke_without_command=True,
    help="Create and manage SMAIRT research workspaces.",
)

# Historical marker from earlier development: commands not yet implemented
# used to be listed here so tests could assert they were still stubs. Every
# command is now real, so this stays empty; test_cli.py checks it stays that
# way (a non-empty tuple would mean a command regressed to a stub).
STUB_COMMANDS: tuple[str, ...] = ()


def _version_callback(value: bool) -> None:
    """Print the version and exit immediately, if ``--version`` was passed.

    Typer calls this as soon as it parses ``--version`` (before running any
    command, because the option is ``is_eager=True`` below) — that's why
    ``smairt --version`` works without needing a subcommand.
    """
    if value:
        typer.echo(f"smairt {__version__}")
        raise typer.Exit()


@app.callback()
def smairt(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the SMAIRT version and exit.",
    ),
) -> None:
    """Create and manage SMAIRT research workspaces."""


def _fail(command: str, message: str) -> NoReturn:
    """Print an error to stderr in the "smairt <command>: <message>" shape, then exit 1.

    Every command's error handling goes through this one function so the
    error format is consistent no matter which command failed. ``NoReturn``
    tells mypy this function never returns normally (it always raises) — so
    callers like :func:`_require_project_root` below don't need an `else`.
    """
    typer.echo(f"smairt {command}: {message}", err=True)
    raise typer.Exit(code=1)


def _require_project_root(command: str) -> Path:
    """Find the current SMAIRT project's root folder, or exit with an error.

    Every command except ``new`` needs to already be inside a project (found
    the same way Git finds its repo root — see
    :func:`smairt.project.find_project_root`). Centralizing this one check
    here means each command below is one line shorter and the "not a SMAIRT
    project" message is worded identically everywhere.

    ``hook`` deliberately does not use this helper — see
    :data:`_HOOK_OUTSIDE_PROJECT_MESSAGE`.
    """
    root = project_module.find_project_root(Path.cwd())
    if root is None:
        _fail(
            command, "not a SMAIRT project (no smairt.yaml found in this or any parent directory)."
        )
    return root


_HOOK_OUTSIDE_PROJECT_MESSAGE = (
    "not inside a SMAIRT project (no smairt.yaml found in this or any parent "
    "directory). If a harness ran this hook outside a project, a smairt entry "
    "likely leaked into your global harness config — remove smairt entries "
    "from e.g. ~/.claude/settings.json or ~/.cursor/hooks.json; generated "
    "wiring belongs only inside a project."
)
"""The ``hook`` command's own "not a project" message — deliberately louder than
:func:`_require_project_root`'s generic one.

Every other command that hits this case was typed by a researcher sitting at a
terminal in the wrong directory; the generic message is enough. ``hook`` is
different: it is almost always invoked unattended by a harness's own hook
runner, not by a human, so the most likely real cause is a stale or
accidentally-global harness config (e.g. a smairt entry copied into
``~/.claude/settings.json`` instead of the project-local file ``smairt
connect`` generates) firing this hook in a directory that was never a SMAIRT
project at all. Naming that cause and its fix here saves a confused researcher
a debugging session. This still exits 1 (via :func:`_fail`), never 2 — a
missing project is not a "findings exist, block the action" signal, and exit 2
must stay reserved for that in harnesses where it means "block".
"""


def _prompt_harness(default: Harness = Harness.claude_code) -> Harness:
    """Prompt for a harness as a numbered choice, re-prompting on a bad answer.

    Accepts either the number or the exact name (``2`` or ``codex``) and
    never lets a typo escape as a raw ``ValueError`` traceback — the one real
    defect in the free-text prompt this replaced. Still a plain
    :func:`typer.prompt` underneath, so piped stdin keeps working the same
    way it always has.
    """
    members = list(Harness)
    typer.secho("Harness:", fg=typer.colors.CYAN, bold=True)
    for index, member in enumerate(members, start=1):
        marker = " (default)" if member is default else ""
        typer.echo(f"  {index}. {member.value}{marker}")
    while True:
        answer = typer.prompt("Choice (number or name)", default=default.value).strip()
        if answer.isdigit():
            position = int(answer)
            if 1 <= position <= len(members):
                return members[position - 1]
        else:
            try:
                return Harness(answer)
            except ValueError:
                pass
        typer.echo(f"'{answer}' isn't one of the choices above — try a number or an exact name.")


def _confirm_or_default(prompt: str, *, default: bool) -> bool:
    """Ask a yes/no question with :func:`typer.confirm`, but only at a real terminal.

    A headless caller -- CI, an assistant harness driving `smairt new` (or
    `smairt adopt`) non-interactively, or a `CliRunner` invocation in tests --
    has no tty for `typer.confirm` to read from, and aborting there is worse
    than silently taking the documented default. So this only prompts when
    ``sys.stdin.isatty()``; otherwise it returns ``default`` unasked -- the
    same value `typer.confirm` would have shown as its own default.
    """
    return typer.confirm(prompt, default=default) if sys.stdin.isatty() else default


def _prompt_missing_identity(
    name: str | None,
    researcher: str | None,
    description: str | None,
    harness: Harness | None,
) -> tuple[str, str, str, Harness]:
    """Prompt for whichever of name/researcher/description/harness is still ``None``.

    Shared by ``new`` and ``adopt`` so the identity prompts — including the
    harness choice — are worded identically no matter which command
    triggered them.
    """
    if name is None:
        name = typer.prompt("Project name")
    if researcher is None:
        researcher = typer.prompt("Researcher")
    if description is None:
        description = typer.prompt("One-line description")
    if harness is None:
        harness = _prompt_harness()
    return name, researcher, description, harness


@app.command()
def new(
    name: str | None = typer.Option(None, "--name", help="Project name."),
    researcher: str | None = typer.Option(None, "--researcher", help="Researcher name."),
    description: str | None = typer.Option(
        None, "--description", help="One-line project description."
    ),
    path: Path | None = typer.Option(
        None, "--path", help="Parent directory for the new project (default: current directory)."
    ),
    harness: Harness | None = typer.Option(
        None, "--harness", help="Assistant harness to record in smairt.yaml."
    ),
    hpc: bool | None = typer.Option(
        None, "--hpc/--no-hpc", help="Also generate hpc/ with a commented SLURM template."
    ),
    paper: bool | None = typer.Option(
        None, "--paper/--no-paper", help="Note paper support under STATUS.md open questions."
    ),
    git: bool | None = typer.Option(
        None,
        "--git/--no-git",
        help="Initialize a Git repository and stage the scaffold (never commits).",
    ),
) -> None:
    """Create a new SMAIRT project: the ten-item day-one scaffold."""
    name, researcher, description, harness = _prompt_missing_identity(
        name, researcher, description, harness
    )
    if hpc is None:
        hpc = _confirm_or_default("Expect to run on HPC/SLURM?", default=False)
    if paper is None:
        paper = _confirm_or_default("Expect this project to support a paper?", default=False)
    if git is None:
        git = _confirm_or_default("Initialize a Git repository?", default=True)

    root = (path or Path.cwd()) / slugify(name, fallback="project")
    try:
        project_module.create_project(
            root,
            name=name,
            researcher=researcher,
            description=description,
            harness=harness,
            hpc=hpc,
            paper=paper,
        )
    except (PathExistsError, ValueError) as error:
        _fail("new", str(error))

    typer.secho(f"Created {root}", fg=typer.colors.GREEN, bold=True)
    if harness is not Harness.none:
        result = connect_module.connect(root, harness, strict=False)
        _report_connect(result)

    # Git init/add runs LAST, after the harness wiring above, so everything
    # `smairt new` generates -- smairt.yaml, AGENTS.md, and the harness's own
    # hook config -- gets staged together, not just the day-one scaffold.
    if git:
        git_result = project_module.init_git(root)
        if git_result.outcome == "initialized":
            typer.echo("Initialized a Git repository and staged the scaffold (nothing committed).")
        elif git_result.outcome == "skipped":
            # Not a warning -- e.g. `root` is nested inside a Git repo that
            # starts above it, so backing off (rather than nesting a second
            # repo inside the first) IS the correct outcome. See
            # smairt.project.init_git's docstring.
            typer.echo(git_result.message)
        else:
            typer.echo(f"Warning: {git_result.message}", err=True)


@app.command()
def adopt(
    name: str | None = typer.Option(None, "--name", help="Project name."),
    researcher: str | None = typer.Option(None, "--researcher", help="Researcher name."),
    description: str | None = typer.Option(
        None, "--description", help="One-line project description."
    ),
    path: Path | None = typer.Option(
        None, "--path", help="Directory to adopt (default: current directory)."
    ),
    harness: Harness | None = typer.Option(
        None, "--harness", help="Assistant harness to record in smairt.yaml."
    ),
) -> None:
    """Adopt a pre-existing directory: lay the contract files around it, move nothing."""
    name, researcher, description, harness = _prompt_missing_identity(
        name, researcher, description, harness
    )

    root = path or Path.cwd()
    try:
        result = adopt_module.adopt_project(
            root,
            name=name,
            researcher=researcher,
            description=description,
            harness=harness,
        )
    except (adopt_module.NotAdoptableError, ValueError) as error:
        _fail("adopt", str(error))

    typer.echo(f"Adopted {root}")
    typer.echo(f"Known folders: {', '.join(result.known_folders) or '(none)'}")
    for written in result.written:
        typer.echo(f"Wrote {written}")
    for unchanged in result.skipped:
        typer.echo(f"Unchanged {unchanged}")
    for warning in result.warned:
        typer.echo(f"Warning: {warning}", err=True)
    if result.connect_result is not None:
        _report_connect(result.connect_result)


@app.command()
def check(
    json_output: bool = typer.Option(
        False, "--json", help="Emit machine-readable JSON instead of human-readable text."
    ),
) -> None:
    """Check a project's state contract: frontmatter, evidence, drift, and more."""
    root = _require_project_root("check")
    report = check_module.run_checks(root)
    if json_output:
        typer.echo(json.dumps(check_module.to_json(report), indent=2))
    else:
        typer.echo(check_module.render_human(report))
    raise typer.Exit(code=report.exit_code)


@app.command()
def hook(
    mode: str = typer.Argument(
        ...,
        help=(
            "'report' prints findings and always exits 0; "
            "'gate' exits 2 while findings exist (the block code harness hooks understand)."
        ),
    ),
) -> None:
    """Run `smairt check` speaking a harness hook's exit-code protocol.

    Generated hook configs (see ``smairt connect``) call this instead of
    ``smairt check`` directly, because the raw check exits 1 on findings and
    hook protocols give exit codes different meanings: Claude Code, Codex, and
    Cursor all treat exit 2 as "block this action and feed stderr back to the
    agent", while exit 1 is a plain non-blocking error. ``gate`` speaks that
    blocking dialect; ``report`` is for session-end hooks that should surface
    findings without ever wedging the harness in a failure loop.
    """
    if mode not in ("report", "gate"):
        _fail("hook", f"unknown mode {mode!r}. Choices: report, gate.")
    root = project_module.find_project_root(Path.cwd())
    if root is None:
        _fail("hook", _HOOK_OUTSIDE_PROJECT_MESSAGE)
    report = check_module.run_checks(root)
    if mode == "report":
        typer.echo(check_module.render_human(report))
        raise typer.Exit(code=0)
    if report.exit_code == 0:
        raise typer.Exit(code=0)
    # Findings exist: block. Stderr is what blocking harnesses relay to the agent.
    typer.echo(check_module.render_human(report), err=True)
    raise typer.Exit(code=2)


@app.command()
def status(
    json_output: bool = typer.Option(
        False, "--json", help="Emit machine-readable JSON instead of human-readable text."
    ),
) -> None:
    """Show project orientation: focus, spine, live/closed questions, and warnings."""
    root = _require_project_root("status")
    report = status_module.build_status_report(root)
    if json_output:
        typer.echo(json.dumps(status_module.to_json(report), indent=2))
    else:
        typer.echo(status_module.render_human(report))


def _report_connect(result: connect_module.ConnectResult) -> None:
    """Print a :class:`~smairt.connect.ConnectResult` the same way after every call.

    Shared by the ``new`` command (which connects a harness automatically),
    ``adopt``, and ``connect`` itself, so "Wrote X" / "Unchanged X" /
    "Warning: ..." always reads identically no matter which command
    triggered the harness wiring.
    """
    for path in result.written:
        typer.echo(f"Wrote {path}")
    for path in result.skipped:
        typer.echo(f"Unchanged {path}")
    for warning in result.warned:
        typer.echo(f"Warning: {warning}", err=True)
    if not (result.written or result.skipped or result.warned):
        typer.echo("Nothing to do.")


@app.command()
def connect(
    harness: str | None = typer.Argument(
        None,
        help=(
            "Harness to wire up (claude-code, codex, opencode, gemini-cli, cursor, pi), "
            "or 'ci' for the GitHub Actions template."
        ),
    ),
    ci: bool = typer.Option(
        False, "--ci", help="Write the GitHub Actions CI template instead of harness wiring."
    ),
) -> None:
    """Wire an assistant harness's hooks to `smairt check` (bridge file + hook config)."""
    root = _require_project_root("connect")

    if ci or harness == "ci":
        _report_connect(connect_module.connect_ci(root))
        return

    if harness is None:
        _fail(
            "connect",
            "a harness is required (claude-code, codex, opencode, gemini-cli, cursor, pi), "
            "or pass --ci.",
        )

    try:
        harness_value = Harness(harness)
    except ValueError:
        choices = ", ".join(member.value for member in Harness if member is not Harness.none)
        _fail("connect", f"unknown harness {harness!r}. Choices: {choices}, ci.")

    if harness_value is Harness.none:
        _fail("connect", "harness 'none' has no wiring to install.")

    strict = connect_module.read_strict_hooks(root)
    _report_connect(connect_module.connect(root, harness_value, strict=strict))


unit_app = typer.Typer(no_args_is_help=True, help="Create units of research.")
app.add_typer(unit_app, name="unit")


@unit_app.command("new")
def unit_new(
    kind: units_module.UnitKind = typer.Argument(..., help="'stage' or 'question'."),
    title: str = typer.Option(..., "--title", help="Unit title."),
    hypothesis: str | None = typer.Option(
        None, "--hypothesis", help="The probe's hypothesis (question units only)."
    ),
    receipt: bool = typer.Option(
        False, "--receipt", help="Record this unit as a receipt for an outside tool."
    ),
    tool: str | None = typer.Option(None, "--tool", help="Outside tool name (with --receipt)."),
    tool_version: str | None = typer.Option(
        None, "--tool-version", help="Outside tool version (with --receipt)."
    ),
    command: str | None = typer.Option(
        None, "--command", help="Exact command that was run (with --receipt)."
    ),
    repo: str | None = typer.Option(
        None, "--repo", help="Tool repo URL and commit, if any (with --receipt)."
    ),
    ref: list[str] = typer.Option(
        [],
        "--ref",
        help=(
            "Existing path this unit references, relative to the project root "
            "(repeatable). Creates a thin, README-only reference unit — case 3, "
            "how pre-existing work gets a unit without moving it."
        ),
    ),
) -> None:
    """Create a stage or question unit under experiments/. The numbering/dating authority."""
    root = _require_project_root("unit new")
    ref_paths = ref or None
    try:
        if kind is units_module.UnitKind.stage:
            unit_dir = units_module.create_stage(
                root,
                title,
                receipt=receipt,
                tool=tool,
                tool_version=tool_version,
                command=command,
                repo=repo,
                ref_paths=ref_paths,
            )
        else:
            unit_dir = units_module.create_question(
                root,
                title,
                hypothesis=hypothesis,
                receipt=receipt,
                tool=tool,
                tool_version=tool_version,
                command=command,
                repo=repo,
                ref_paths=ref_paths,
            )
    except (PathExistsError, ValueError) as error:
        _fail("unit new", str(error))

    typer.echo(f"Created {unit_dir.relative_to(root)}")


data_app = typer.Typer(no_args_is_help=True, help="Record where each dataset physically lives.")
app.add_typer(data_app, name="data")


def _parse_hpc_location(value: str, note: str | None) -> data_module.Location:
    """Parse a ``--hpc HOST:PATH`` flag into a :class:`~smairt.data.Location`.

    Fails cleanly (a plain ``ValueError``, not an unhandled ``IndexError``
    from a bad ``.split()``) when ``value`` has no ``:`` separator at all.
    """
    if ":" not in value:
        raise ValueError(f"--hpc expects HOST:PATH (got {value!r}, with no ':')")
    host, path = value.split(":", 1)
    if not host.strip() or not path.strip():
        raise ValueError(f"--hpc expects HOST:PATH, both non-empty (got {value!r})")
    return data_module.Location(kind="hpc", host=host, path=path, note=note)


def _collect_new_locations(
    hpc: list[str], url: list[str], local: list[str], note: str | None
) -> list[data_module.Location]:
    """Turn ``data new``'s repeatable location flags into a list of :class:`~smairt.data.Location`.

    ``--note`` is not repeatable, so if it is given alongside more than one
    location flag it is applied to every location created in this one call
    -- a deliberate simplification for the common case (one dataset, one
    note about how it was obtained), not per-location notes.
    """
    locations: list[data_module.Location] = []
    for value in hpc:
        locations.append(_parse_hpc_location(value, note))
    for value in url:
        locations.append(data_module.Location(kind="url", path=value, note=note))
    for value in local:
        locations.append(data_module.Location(kind="local", path=value, note=note))
    return locations


@data_app.command("new")
def data_new(
    name: str = typer.Argument(..., help="Dataset name; slugified into data/<slug>/."),
    hpc: list[str] = typer.Option([], "--hpc", help="An HPC location, as HOST:PATH (repeatable)."),
    url: list[str] = typer.Option([], "--url", help="A download-source URL (repeatable)."),
    local: list[str] = typer.Option(
        [], "--local", help="An additional local path, beyond the dataset folder (repeatable)."
    ),
    note: str | None = typer.Option(
        None, "--note", help="Note applied to every location passed above."
    ),
) -> None:
    """Create data/<slug>/README.md, recording where this dataset's bytes live."""
    root = _require_project_root("data new")
    try:
        locations = _collect_new_locations(hpc, url, local, note)
        dataset_dir = data_module.create_dataset(root, name, locations=locations)
    except (PathExistsError, ValueError) as error:
        _fail("data new", str(error))

    typer.echo(f"Created {dataset_dir.relative_to(root)}")


@data_app.command("locate")
def data_locate(
    name: str = typer.Argument(..., help="Dataset name (as passed to `smairt data new`)."),
    hpc: str | None = typer.Option(None, "--hpc", help="An HPC location, as HOST:PATH."),
    url: str | None = typer.Option(None, "--url", help="A download-source URL."),
    local: str | None = typer.Option(None, "--local", help="A local path."),
    note: str | None = typer.Option(None, "--note", help="Optional note for this location."),
) -> None:
    """Add one location to an existing dataset's README frontmatter."""
    root = _require_project_root("data locate")
    given = [value for value in (hpc, url, local) if value is not None]
    if len(given) != 1:
        _fail("data locate", "exactly one of --hpc, --url, --local is required.")

    try:
        if hpc is not None:
            location = _parse_hpc_location(hpc, note)
        elif url is not None:
            location = data_module.Location(kind="url", path=url, note=note)
        else:
            assert local is not None
            location = data_module.Location(kind="local", path=local, note=note)
        dataset_dir = data_module.add_location(root, name, location)
    except ValueError as error:
        _fail("data locate", str(error))

    typer.echo(f"Updated {dataset_dir.relative_to(root)}/README.md")


@data_app.command("list")
def data_list(
    json_output: bool = typer.Option(
        False, "--json", help="Emit machine-readable JSON instead of human-readable text."
    ),
) -> None:
    """List every dataset under data/ and every location recorded for it."""
    root = _require_project_root("data list")
    report = data_module.list_locations(root)
    if json_output:
        typer.echo(json.dumps(data_module.to_json(report), indent=2))
    else:
        typer.echo(data_module.render_human(report))


@app.command()
def index() -> None:
    """Regenerate results/INDEX.md from every unit's frontmatter header."""
    root = _require_project_root("index")
    path = index_module.write_index(root)
    typer.echo(f"Updated {path.relative_to(root)}")


def main() -> None:
    """The actual entry point installed as the ``smairt`` console script.

    Just hands off to Typer's ``app()``, which parses ``sys.argv`` and
    dispatches to whichever ``@app.command()`` function matches.
    """
    app()


if __name__ == "__main__":
    main()
