"""Schema-v4 credential, ingestion, MCP, and harness safety contracts."""

import asyncio
import io
import json
import os
import sys
import tomllib
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError
from pypdf import PdfWriter

from smairt.credentials import (
    CredentialBackendLocked,
    delete_credential,
    keyring_health,
    resolve_credential,
    set_credential,
)
from smairt.harnesses import MCP_TOOL_NAMES, configure_mcp, select_harness
from smairt.mcp_server import _reference_allowed, build_server
from smairt.migrations import apply_migration, rollback_migration
from smairt.models import (
    DataClassification,
    EnvironmentMode,
    HarnessName,
    ReferenceRecord,
    SmairtConfig,
    VerificationStatus,
    ZoteroLibraryType,
    ZoteroMode,
)
from smairt.provenance import add_contributor
from smairt.references import (
    add_doi_reference,
    copy_zotero_attachment,
    import_zotero_collection,
    load_index,
)
from smairt.scaffold import create_project
from smairt.settings import select_environment
from smairt.zotero import ZoteroProvider


def project(tmp_path: Path, harness: HarnessName = HarnessName.CODEX) -> Path:
    root = tmp_path / "v4-project"
    create_project(
        root,
        name="Literature",
        author="Researcher",
        classification=DataClassification.UNPUBLISHED,
        initialize_git=False,
        confirm_contributor=True,
        harness=harness,
    )
    return root


class FakeKeyring:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, account: str) -> str | None:
        return self.values.get((service, account))

    def set_password(self, service: str, account: str, value: str) -> None:
        self.values[(service, account)] = value

    def delete_password(self, service: str, account: str) -> None:
        del self.values[(service, account)]


def test_credentials_use_environment_first_and_never_enter_config(
    monkeypatch, tmp_path: Path
) -> None:
    root = project(tmp_path)
    backend = FakeKeyring()
    monkeypatch.setattr("smairt.credentials._keyring", lambda: backend)
    set_credential("openalex", "lab", "keyring-secret")
    monkeypatch.setenv("OPENALEX_API_KEY", "environment-secret")
    value, resolution = resolve_credential("openalex", "lab", "OPENALEX_API_KEY")
    assert value == "environment-secret"
    assert resolution and resolution.source.startswith("environment:")
    assert "secret" not in (root / "smairt.yaml").read_text()
    assert delete_credential("openalex", "lab")


def test_reference_attachment_fields_are_optional_together() -> None:
    assert ReferenceRecord(id="metadata-only", title="Metadata").local_path is None
    with pytest.raises(ValidationError, match="provided together"):
        ReferenceRecord(id="broken", title="Broken", local_path="pdfs/a.pdf")


def test_doi_add_is_metadata_only_and_deduplicates(monkeypatch, tmp_path: Path) -> None:
    root = project(tmp_path)
    raw = {
        "message": {
            "title": ["A trustworthy paper"],
            "author": [{"given": "A", "family": "Researcher"}],
            "published": {"date-parts": [[2025]]},
        }
    }
    monkeypatch.setattr("smairt.references._fetch_crossref", lambda _doi: raw)
    first = add_doi_reference(root, "https://doi.org/10.1000/Example")
    second = add_doi_reference(root, "doi:10.1000/example")
    assert first.id == second.id
    assert first.local_path is None and first.sha256 is None
    assert len(load_index(root)) == 1
    assert yaml.safe_load((root / "references/index.yaml").read_text())["schema_version"] == 2


def test_v3_to_v4_backs_up_config_and_reference_index(tmp_path: Path) -> None:
    root = project(tmp_path)
    config_path = root / "smairt.yaml"
    payload = yaml.safe_load(config_path.read_text())
    payload["schema_version"] = 3
    payload.pop("integrations")
    config_path.write_text(yaml.safe_dump(payload, sort_keys=False))
    index = root / "references/index.yaml"
    index.write_text("references: []\n")
    record = apply_migration(root, allow_dirty=True)
    assert SmairtConfig.load(config_path).schema_version == 4
    assert set(record["backups"]) == {"smairt.yaml", "references/index.yaml"}
    assert yaml.safe_load(index.read_text())["schema_version"] == 2
    index.write_text(index.read_text() + "# researcher edit\n")
    with pytest.raises(ValueError, match=r"references/index\.yaml"):
        rollback_migration(root)


def test_legacy_config_writes_do_not_gain_newer_schema_fields(tmp_path: Path) -> None:
    root = project(tmp_path)
    config = SmairtConfig.load(root / "smairt.yaml")
    config.schema_version = 2
    config.dump(root / "smairt.yaml")
    add_contributor(root, "Legacy Collaborator")
    select_environment(root, mode=EnvironmentMode.NONE)
    select_harness(root, "zoo")
    payload = yaml.safe_load((root / "smairt.yaml").read_text())
    assert "integrations" not in payload
    assert "fields_of_study" not in payload["project"]
    assert "license" not in payload["project"]


def test_doi_openalex_failure_is_atomic(monkeypatch, tmp_path: Path) -> None:
    root = project(tmp_path)
    before = (root / "references/index.yaml").read_bytes()
    monkeypatch.setattr(
        "smairt.references._fetch_crossref",
        lambda _doi: {"message": {"title": ["Fetched first"]}},
    )
    monkeypatch.setattr("smairt.references._resolve_openalex_key", lambda *_args: "secret")

    def fail_openalex(*_args):
        raise RuntimeError("supplement failed")

    monkeypatch.setattr("smairt.references._fetch_openalex", fail_openalex)
    with pytest.raises(RuntimeError, match="supplement failed"):
        add_doi_reference(root, "10.1000/atomic", use_openalex=True)
    assert (root / "references/index.yaml").read_bytes() == before
    assert not list((root / "references/provenance").rglob("*.json"))


def test_collection_import_uses_paginated_records_without_refetch(
    monkeypatch, tmp_path: Path
) -> None:
    root = project(tmp_path)

    class FakeConfig:
        library_type = type("LibraryType", (), {"value": "user"})()

    class FakeProvider:
        config = FakeConfig()

        def __init__(self, _root):
            pass

        def collection_items(self, key, limit):
            assert key == "COLLECTION" and limit == 2
            return [
                {"key": "ITEM1", "data": {"key": "ITEM1", "title": "First"}},
                {"key": "ITEM2", "data": {"key": "ITEM2", "title": "Second"}},
            ]

        def item(self, _key):
            raise AssertionError("collection imports must not refetch items")

    monkeypatch.setattr("smairt.zotero.ZoteroProvider", FakeProvider)
    imported = import_zotero_collection(root, "COLLECTION", limit=2)
    assert [record.title for record in imported] == ["First", "Second"]


def test_mcp_inventory_and_generated_harness_configs(tmp_path: Path) -> None:
    root = project(tmp_path)
    server = build_server(root)
    assert set(server._tool_manager._tools) == set(MCP_TOOL_NAMES)
    parsed = tomllib.loads((root / ".codex/config.toml").read_text())
    assert "mcp_servers" not in parsed
    hooks = json.loads((root / ".codex/hooks.json").read_text())
    assert hooks["hooks"]["PreToolUse"][0]["hooks"][0]["type"] == "command"
    enabled = configure_mcp(root, HarnessName.CODEX, True)
    assert enabled["changed"] is True
    parsed = tomllib.loads((root / ".codex/config.toml").read_text())
    assert parsed["mcp_servers"]["smairt"]["enabled_tools"] == MCP_TOOL_NAMES
    before = (root / ".smairt/harnesses/codex.json").read_bytes()
    assert configure_mcp(root, HarnessName.CODEX, True)["changed"] is False
    assert (root / ".smairt/harnesses/codex.json").read_bytes() == before
    assert configure_mcp(root, HarnessName.CODEX, False)["changed"] is True
    parsed = tomllib.loads((root / ".codex/config.toml").read_text())
    assert "mcp_servers" not in parsed
    hooks = json.loads((root / ".codex/hooks.json").read_text())
    assert hooks["hooks"]["PreToolUse"][0]["hooks"][0]["type"] == "command"
    assert not any(
        "KEY" in value for value in os.environ if value in (root / ".codex/config.toml").read_text()
    )

    zoo = project(tmp_path / "zoo", HarnessName.ZOO)
    assert not (zoo / ".roo/mcp.json").exists()
    configure_mcp(zoo, HarnessName.ZOO, True)
    zoo_config = json.loads((zoo / ".roo/mcp.json").read_text())
    assert zoo_config["mcpServers"]["smairt"]["alwaysAllow"] == MCP_TOOL_NAMES
    zoo_config["mcpServers"]["custom"] = {"command": "custom-server"}
    (zoo / ".roo/mcp.json").write_text(json.dumps(zoo_config))
    configure_mcp(zoo, HarnessName.ZOO, False)
    zoo_config = json.loads((zoo / ".roo/mcp.json").read_text())
    assert "smairt" not in zoo_config["mcpServers"]
    assert zoo_config["mcpServers"]["custom"] == {"command": "custom-server"}


def test_mcp_public_sdk_and_real_stdio_exclude_private_fields(monkeypatch, tmp_path: Path) -> None:
    root = project(tmp_path)
    monkeypatch.setattr(
        "smairt.references._fetch_crossref",
        lambda _doi: {
            "message": {
                "title": ["Safe metadata"],
                "author": [{"given": "A", "family": "Researcher"}],
            }
        },
    )
    add_doi_reference(root, "10.1000/mcp-safe")

    async def exercise() -> None:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        from mcp.shared.memory import create_connected_server_and_client_session

        server = build_server(root)
        async with create_connected_server_and_client_session(server) as client:
            tools = await client.list_tools()
            assert [tool.name for tool in tools.tools] == list(MCP_TOOL_NAMES)
            assert all(tool.annotations and tool.annotations.readOnlyHint for tool in tools.tools)
            result = await client.call_tool("reference_search", {"query": "Safe", "limit": 1})
            rendered = json.dumps(result.model_dump(mode="json"))
            assert "snapshot" not in rendered and "sha256" not in rendered
            assert "edit_history" not in rendered and "local_path" not in rendered

        code = "from pathlib import Path; from smairt.mcp_server import serve; serve(Path.cwd())"
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-c", code],
            cwd=root,
        )
        async with (
            stdio_client(parameters) as (read, write),
            ClientSession(read, write) as client,
        ):
            await client.initialize()
            tools = await client.list_tools()
            assert [tool.name for tool in tools.tools] == list(MCP_TOOL_NAMES)

    asyncio.run(exercise())


def test_mcp_reference_tools_block_controlled_projects(tmp_path: Path) -> None:
    """Keep controlled bibliographies out of the metadata-only MCP surface."""
    root = tmp_path / "controlled-mcp"
    create_project(
        root,
        name="Controlled MCP",
        author="Researcher",
        classification=DataClassification.CONTROLLED,
        initialize_git=False,
        confirm_contributor=True,
    )
    with pytest.raises(ValueError, match="controlled"):
        _reference_allowed(root)


def test_keyring_locked_and_null_backends_are_typed_and_secret_free(monkeypatch) -> None:
    from keyring import errors

    class Locked:
        def get_password(self, _service, _account):
            raise errors.KeyringLocked("do-not-leak-secret")

    monkeypatch.setattr("smairt.credentials._keyring", lambda: Locked())
    with pytest.raises(CredentialBackendLocked) as caught:
        resolve_credential("openalex", "default")
    assert "do-not-leak-secret" not in str(caught.value)

    class NullBackend:
        priority = 0

    class NullKeyring:
        def get_keyring(self):
            return NullBackend()

    monkeypatch.setattr("smairt.credentials._keyring", lambda: NullKeyring())
    assert keyring_health()["status"] == "null"


def test_duplicate_doi_preserves_legacy_id_and_human_metadata(monkeypatch, tmp_path: Path) -> None:
    root = project(tmp_path)
    record = ReferenceRecord(
        id="legacy-slug-id",
        title="Human title",
        authors=["Human Author"],
        doi="10.1000/preserved",
        metadata_verified=True,
        verification_status=VerificationStatus.VERIFIED,
        edit_history=[{"field": "venue", "value": "Manual venue"}],
        venue="Manual venue",
    )
    (root / "references/index.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 2,
                "references": [record.model_dump(mode="json", exclude_none=True)],
            },
            sort_keys=False,
        )
    )
    monkeypatch.setattr(
        "smairt.references._fetch_crossref",
        lambda _doi: {
            "message": {
                "title": ["Provider title"],
                "author": [{"family": "Provider"}],
                "container-title": ["Provider venue"],
            }
        },
    )
    merged = add_doi_reference(root, "10.1000/preserved")
    assert merged.id == "legacy-slug-id"
    assert merged.title == "Human title" and merged.authors == ["Human Author"]
    assert merged.venue == "Manual venue"
    assert merged.verification_status is VerificationStatus.VERIFIED


def test_zotero_provider_paginates_and_rejects_unbounded_limits(tmp_path: Path) -> None:
    root = project(tmp_path)
    from smairt.integrations import configure_zotero

    configure_zotero(
        root,
        mode=ZoteroMode.LOCAL,
        library_id=None,
        library_type=ZoteroLibraryType.USER,
        profile="pagination",
    )

    class FakeClient:
        request = type("Request", (), {"headers": {"Last-Modified-Version": "42"}})()

        def __init__(self):
            self.links = {"next": "next"}

        def collection_items(self, _key, **kwargs):
            assert kwargs["v"] == 3 and kwargs["limit"] == 2
            return [{"key": "A"}]

        def follow(self, **kwargs):
            assert kwargs["v"] == 3
            self.links = {}
            return [{"key": "B"}]

    provider = ZoteroProvider(root, client_factory=lambda _config, _timeout: FakeClient())
    assert [item["key"] for item in provider.collection_items("COLL", 2)] == ["A", "B"]
    assert provider.last_library_version == "42"
    with pytest.raises(ValueError, match="between 1 and 1000"):
        provider.collection_items("COLL", 1001)


def test_local_zotero_attachment_is_one_atomic_transaction(monkeypatch, tmp_path: Path) -> None:
    root = project(tmp_path)
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buffer = io.BytesIO()
    writer.write(buffer)
    pdf = buffer.getvalue()

    class FakeConfig:
        mode = ZoteroMode.LOCAL
        library_type = type("LibraryType", (), {"value": "user"})()

    class FakeProvider:
        config = FakeConfig()

        def __init__(self, _root):
            pass

        def item(self, key):
            return {"key": key, "data": {"key": key, "title": "Atomic attachment"}}

        def children(self, _key):
            return [{"key": "PDF1", "data": {"key": "PDF1"}}]

        def local_attachment(self, key):
            return {"key": key, "data": {"itemType": "attachment"}}, pdf

    monkeypatch.setattr("smairt.zotero.ZoteroProvider", FakeProvider)
    saved = copy_zotero_attachment(root, "ITEM1", "PDF1", confirmed=True)
    assert saved.local_path and saved.sha256
    assert (root / "references" / saved.local_path).read_bytes() == pdf
    assert len(load_index(root)) == 1
