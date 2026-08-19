from __future__ import annotations

import json
from pathlib import Path
from typing import NoReturn

import typer

from smairt import __version__
from smairt import adopt as adopt_module
from smairt import check as check_module
from smairt import connect as connect_module
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

STUB_COMMANDS: tuple[str, ...] = ()


def _version_callback(value: bool) -> None:
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
    typer.echo(f"smairt {command}: {message}", err=True)
    raise typer.Exit(code=1)


def _require_project_root(command: str) -> Path:
    root = project_module.find_project_root(Path.cwd())
    if root is None:
        _fail(
            command, "not a SMAIRT project (no smairt.yaml found in this or any parent directory)."
        )
    return root


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
) -> None:
    """Create a new SMAIRT project: the ten-item day-one scaffold."""
    if name is None:
        name = typer.prompt("Project name")
    if researcher is None:
        researcher = typer.prompt("Researcher")
    if description is None:
        description = typer.prompt("One-line description")
    if harness is None:
        choices = ", ".join(member.value for member in Harness)
        harness = Harness(typer.prompt(f"Harness ({choices})", default=Harness.claude_code.value))
    if hpc is None:
        hpc = typer.confirm("Expect to run on HPC/SLURM?", default=False)
    if paper is None:
        paper = typer.confirm("Expect this project to support a paper?", default=False)

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

    typer.echo(f"Created {root}")
    if harness is not Harness.none:
        result = connect_module.connect(root, harness, strict=False)
        _report_connect(result)


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
    if name is None:
        name = typer.prompt("Project name")
    if researcher is None:
        researcher = typer.prompt("Researcher")
    if description is None:
        description = typer.prompt("One-line description")
    if harness is None:
        choices = ", ".join(member.value for member in Harness)
        harness = Harness(typer.prompt(f"Harness ({choices})", default=Harness.claude_code.value))

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
            "Harness to wire up (claude-code, codex, opencode, gemini-cli, cursor), "
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
            "a harness is required (claude-code, codex, opencode, gemini-cli, cursor), "
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


@app.command()
def index() -> None:
    """Regenerate results/INDEX.md from every unit's frontmatter header."""
    root = _require_project_root("index")
    path = index_module.write_index(root)
    typer.echo(f"Updated {path.relative_to(root)}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
