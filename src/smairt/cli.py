from __future__ import annotations

import typer

from smairt import __version__

app = typer.Typer(
    no_args_is_help=True,
    invoke_without_command=True,
    help="Create and manage SMAIRT research workspaces.",
)

STUB_COMMANDS = ("new", "check", "status", "connect", "unit")


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


def _stub(name: str) -> None:
    typer.echo(f"smairt {name}: arrives in a later work package.")
    raise typer.Exit(code=1)


@app.command()
def new() -> None:
    """Create a new SMAIRT project. Not yet implemented."""
    _stub("new")


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


@app.command()
def unit() -> None:
    """Create a new unit of research. Not yet implemented."""
    _stub("unit")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
