"""Literature discovery and explicit open-access retrieval commands."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console
from rich.prompt import Confirm

from smairt.cli_shared import emit, project_root
from smairt.literature import (
    literature_access,
    literature_recommend,
    literature_related,
    literature_search,
)

literature_app = typer.Typer(help="Discover literature and resolve open-access copies")
console = Console()


@literature_app.command("search")
def search_command(
    query: Annotated[str, typer.Argument()],
    provider: Annotated[str, typer.Option("--provider")] = "openalex",
    limit: Annotated[int, typer.Option("--limit", min=1, max=50)] = 20,
    confirm_remote: Annotated[bool, typer.Option("--confirm-remote")] = False,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Search provisional candidates without importing them."""
    payload = [
        item.model_dump(mode="json", exclude_none=True)
        for item in literature_search(
            project_root(), query, limit, provider, confirm_remote=confirm_remote
        )
    ]
    emit(payload, as_json)


@literature_app.command("related")
def related_command(
    identifier: Annotated[str, typer.Argument()],
    direction: Annotated[str, typer.Option("--direction")],
    provider: Annotated[str, typer.Option("--provider")] = "openalex",
    limit: Annotated[int, typer.Option("--limit", min=1, max=50)] = 20,
    confirm_remote: Annotated[bool, typer.Option("--confirm-remote")] = False,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """List bounded references or citing works for one indexed DOI."""
    payload = [
        item.model_dump(mode="json", exclude_none=True)
        for item in literature_related(
            project_root(),
            identifier,
            direction,
            limit,
            provider,
            confirm_remote=confirm_remote,
        )
    ]
    emit(payload, as_json)


@literature_app.command("recommend")
def recommend_command(
    identifier: Annotated[str, typer.Argument()],
    limit: Annotated[int, typer.Option("--limit", min=1, max=50)] = 20,
    confirm_remote: Annotated[bool, typer.Option("--confirm-remote")] = False,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Recommend provisional Semantic Scholar papers from one project reference."""
    payload = [
        item.model_dump(mode="json", exclude_none=True)
        for item in literature_recommend(
            project_root(), identifier, limit, confirm_remote=confirm_remote
        )
    ]
    emit(payload, as_json)


@literature_app.command("access")
def access_command(
    identifier: Annotated[str, typer.Argument()],
    download: Annotated[bool, typer.Option("--download")] = False,
    yes: Annotated[bool, typer.Option("--yes")] = False,
    confirm_remote: Annotated[bool, typer.Option("--confirm-remote")] = False,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Show an OA source and optionally download a validated managed copy."""
    root = project_root()
    preview = literature_access(root, identifier, confirm_remote=confirm_remote)
    if not download:
        emit(preview, as_json)
        return
    location = preview["location"]
    if not as_json:
        console.print(location)
    if not yes and not Confirm.ask("Download this source into references/pdfs?", default=False):
        raise typer.Exit()
    result = literature_access(
        root,
        identifier,
        download=True,
        confirmed=True,
        confirm_remote=confirm_remote,
    )
    result["request_count"] = 2
    emit(result, as_json)
