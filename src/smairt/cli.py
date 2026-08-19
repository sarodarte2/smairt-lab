from __future__ import annotations

from pathlib import Path
from typing import NoReturn

import typer

from smairt import __version__
from smairt import index as index_module
from smairt import project as project_module
from smairt import units as units_module
from smairt.fsutil import PathExistsError
from smairt.project import Harness
from smairt.text import slugify

app = typer.Typer(
    no_args_is_help=True,
    invoke_without_command=True,
    help="Create and manage SMAIRT research workspaces.",
)

STUB_COMMANDS = ("check", "status", "connect")


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


def _stub(name: str) -> NoReturn:
    typer.echo(f"smairt {name}: arrives in a later work package.")
    raise typer.Exit(code=1)


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
        typer.echo(
            f"Harness wiring for {harness.value} arrives with `smairt connect` in a later work package."
        )


@app.command()
def check() -> None:
    """Check a project's state contract. Not yet implemented."""
    _stub("check")


@app.command()
def status() -> None:
    """Show project orientation. Not yet implemented."""
    _stub("status")


@app.command()
def connect() -> None:
    """Connect an assistant harness to a project. Not yet implemented."""
    _stub("connect")


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
) -> None:
    """Create a stage or question unit under experiments/. The numbering/dating authority."""
    root = _require_project_root("unit new")
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
