"""Bounded read-only MCP server for project and optional Zotero metadata."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from smairt.models import DataClassification, SmairtConfig
from smairt.references import get_reference, load_index
from smairt.zotero import ZoteroProvider, public_item

MCP_TOOL_NAMES = (
    "reference_search",
    "reference_get",
    "zotero_search",
    "zotero_get_item",
    "zotero_list_collections",
)
MAX_RESULTS = 50
MAX_QUERY_LENGTH = 500


def _limit(value: int) -> int:
    if value < 1 or value > MAX_RESULTS:
        raise ValueError(f"limit must be between 1 and {MAX_RESULTS}")
    return value


def _query(value: str) -> str:
    """Validate a bounded search query before reading an index or provider."""
    query = value.strip()
    if not query or len(query) > MAX_QUERY_LENGTH:
        raise ValueError(f"query must contain 1 to {MAX_QUERY_LENGTH} characters")
    return query


def _public_reference(record: Any) -> dict[str, Any]:
    """Build an allow-listed DTO with no attachment, snapshot, or edit data."""
    fields = (
        "id",
        "title",
        "authors",
        "year",
        "doi",
        "document_type",
        "citation_key",
        "identifiers",
        "publication_date",
        "venue",
        "volume",
        "issue",
        "pages",
        "publisher",
        "url",
        "license",
        "metadata_verified",
        "verification_status",
    )
    payload = {field: getattr(record, field) for field in fields}
    payload["verification_status"] = record.verification_status.value
    payload["provenance_sources"] = sorted(
        {
            str(entry.get("source"))
            for entry in record.source_provenance
            if isinstance(entry, dict) and entry.get("source")
        }
    )
    return {key: value for key, value in payload.items() if value is not None}


def _zotero_allowed(root: Path) -> None:
    config = SmairtConfig.load(root / "smairt.yaml")
    if config.data.classification is DataClassification.CONTROLLED:
        raise ValueError("controlled projects cannot expose Zotero through MCP")
    zotero = config.integrations.zotero
    if not zotero.mcp_access_enabled:
        raise ValueError("Zotero MCP access is disabled")
    if config.data.classification is DataClassification.PRIVATE and not (
        zotero.mcp_confirmed_by and zotero.mcp_confirmed_at
    ):
        raise ValueError("private projects require attributed Zotero MCP confirmation")


def _reference_allowed(root: Path) -> None:
    """Gate project bibliography tools with the same classification posture as Zotero."""
    config = SmairtConfig.load(root / "smairt.yaml")
    if config.data.classification is DataClassification.CONTROLLED:
        raise ValueError("controlled projects cannot expose the reference index through MCP")
    if config.data.classification is DataClassification.PRIVATE:
        attestation = config.repository_attestation
        if not (
            attestation.acknowledged and attestation.contributor_id and attestation.acknowledged_at
        ):
            raise ValueError(
                "private projects require a repository visibility attestation before "
                "exposing the reference index through MCP"
            )


def build_server(root: Path) -> Any:
    """Build the exact five-tool server without starting a transport."""
    try:
        from mcp.server.fastmcp import FastMCP
        from mcp.types import ToolAnnotations
    except ImportError as exc:
        raise RuntimeError("MCP support is not installed") from exc

    server = FastMCP("SMAIRT read-only literature")
    read_only = ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
    )

    @server.tool(annotations=read_only)
    def reference_search(query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Search bounded project-index metadata; never return PDF or full text."""
        _reference_allowed(root)
        requested = _limit(limit)
        needle = _query(query).casefold()
        matches = []
        for record in load_index(root):
            haystack = " ".join([record.title, *record.authors, record.doi or ""]).casefold()
            if needle in haystack:
                matches.append(_public_reference(record))
            if len(matches) >= requested:
                break
        return matches

    @server.tool(annotations=read_only)
    def reference_get(identifier: str) -> dict[str, Any]:
        """Get one project-index metadata record by validated identifier."""
        _reference_allowed(root)
        return _public_reference(get_reference(root, identifier))

    @server.tool(annotations=read_only)
    def zotero_search(query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Search explicitly enabled read-only Zotero metadata."""
        requested = _limit(limit)
        validated_query = _query(query)
        _zotero_allowed(root)
        return [
            public_item(item) for item in ZoteroProvider(root).search(validated_query, requested)
        ]

    @server.tool(annotations=read_only)
    def zotero_get_item(item_key: str) -> dict[str, Any]:
        """Get one explicitly enabled Zotero metadata item."""
        _zotero_allowed(root)
        return public_item(ZoteroProvider(root).item(item_key))

    @server.tool(annotations=read_only)
    def zotero_list_collections(limit: int = 20) -> list[dict[str, Any]]:
        """List bounded Zotero collection names and keys."""
        requested = _limit(limit)
        _zotero_allowed(root)
        output = []
        for collection in ZoteroProvider(root).collections(requested):
            data_value = collection.get("data")
            data: dict[str, Any] = data_value if isinstance(data_value, dict) else {}
            output.append(
                {
                    "key": collection.get("key") or data.get("key"),
                    "name": data.get("name"),
                    "parentCollection": data.get("parentCollection"),
                }
            )
        return output

    return server


def serve(root: Path) -> None:
    """Run JSON-RPC over stdio; application diagnostics remain on stderr."""
    build_server(root).run(transport="stdio")
