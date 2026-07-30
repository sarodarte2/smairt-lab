"""DataCite fallback, literature discovery, OA safety, and PDF organization tests."""

from __future__ import annotations

import io
import json
import urllib.error
from pathlib import Path

import httpx
import pytest
from pypdf import PdfWriter

from smairt.integrations import configure_openalex
from smairt.literature import (
    OpenAlexProvider,
    literature_access,
    literature_search,
    safe_download_pdf,
)
from smairt.local_setup import ConnectionProfile, bind_profile, configure_profile
from smairt.models import (
    AccessLocation,
    DataClassification,
    ReferenceRecord,
    SafetyMode,
    SmairtConfig,
)
from smairt.references import (
    add_doi_reference,
    add_reference,
    load_index,
    managed_pdf_filename,
    organize_pdfs,
    save_index,
)
from smairt.scaffold import create_project


def project(tmp_path: Path) -> Path:
    root = tmp_path / "literature-v7"
    create_project(
        root,
        name="Literature v7",
        author="Researcher",
        classification=DataClassification.UNPUBLISHED,
        initialize_git=False,
        confirm_contributor=True,
    )
    return root


def pdf_bytes() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


class JsonResponse:
    def __init__(self, payload: dict[str, object]):
        self.payload = payload
        self.headers: dict[str, str] = {}
        self.status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, *_args) -> bytes:
        return json.dumps(self.payload).encode()


def test_datacite_is_used_only_after_crossref_404(monkeypatch, tmp_path: Path) -> None:
    root = project(tmp_path)
    calls = 0

    def fallback(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise urllib.error.HTTPError("url", 404, "missing", {}, None)
        return JsonResponse(
            {
                "data": {
                    "attributes": {
                        "titles": [{"title": "DataCite dataset"}],
                        "creators": [{"name": "Ada Author"}],
                        "publicationYear": 2025,
                        "publisher": "Repository",
                    }
                }
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fallback)
    record = add_doi_reference(root, "10.1234/datacite")
    assert record.title == "DataCite dataset"
    assert record.source_provenance[-1]["source"] == "datacite"
    assert calls == 2

    calls = 0

    def server_error(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise urllib.error.HTTPError("url", 500, "failure", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", server_error)
    with pytest.raises(Exception, match="Crossref request failed with HTTP 500"):
        add_doi_reference(root, "10.1234/no-fallback")
    assert calls == 1


def test_openalex_search_is_bounded_and_reports_budget(monkeypatch, tmp_path: Path) -> None:
    root = project(tmp_path)
    monkeypatch.setenv("OPENALEX_API_KEY", "test-key")
    configure_openalex(root, enabled=True, profile="default")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["per-page"] == "20"
        return httpx.Response(
            200,
            headers={"X-RateLimit-Remaining": "0.98"},
            json={
                "results": [
                    {
                        "id": "https://openalex.org/W1",
                        "title": "Candidate",
                        "doi": None,
                        "publication_year": 2024,
                        "authorships": [],
                        "primary_location": None,
                    }
                ]
            },
        )

    provider = OpenAlexProvider(root, client=httpx.Client(transport=httpx.MockTransport(handler)))
    result = provider.search("candidate")
    assert result[0].doi is None
    assert result[0].remaining_budget == "0.98"
    with pytest.raises(ValueError, match="between 1 and 50"):
        provider.search("candidate", 51)


def test_safe_download_rejects_private_hosts_and_accepts_valid_pdf() -> None:
    data = pdf_bytes()
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, content=data))
    )
    public = lambda *_args, **_kwargs: [  # noqa: E731
        (2, 1, 6, "", ("93.184.216.34", 443))
    ]
    downloaded = safe_download_pdf("https://example.org/paper.pdf", client=client, resolver=public)
    assert downloaded == data
    private = lambda *_args, **_kwargs: [(2, 1, 6, "", ("127.0.0.1", 443))]  # noqa: E731
    with pytest.raises(ValueError, match="private or reserved"):
        safe_download_pdf("https://example.org/paper.pdf", client=client, resolver=private)


def test_unpaywall_download_is_atomic_and_email_stays_local(monkeypatch, tmp_path: Path) -> None:
    root = project(tmp_path)
    configure_profile(
        "default", ConnectionProfile(provider="unpaywall", contact_email="researcher@example.org")
    )
    bind_profile(root, "unpaywall", "default")
    save_index(
        root,
        [
            ReferenceRecord(
                id="oa-record",
                title="Open access",
                authors=["Ada Author"],
                year=2024,
                doi="10.1234/open",
            )
        ],
    )

    class FakeProvider:
        def __init__(self, _root):
            self.last_snapshot = {"doi": "10.1234/open", "is_oa": True}

        def lookup(self, record):
            return AccessLocation(
                reference_id=record.id,
                doi=record.doi,
                url="https://example.org/open.pdf",
                host="example.org",
                license="cc-by",
                version="publishedVersion",
                direct_pdf=True,
            )

    monkeypatch.setattr("smairt.literature.UnpaywallProvider", FakeProvider)
    monkeypatch.setattr(
        "smairt.literature.safe_download_pdf", lambda *_args, **_kwargs: pdf_bytes()
    )
    result = literature_access(root, "oa-record", download=True, confirmed=True)
    assert result["downloaded"] is True
    saved = load_index(root)[0]
    assert saved.local_path and (root / "references" / saved.local_path).is_file()
    assert "researcher@example.org" not in (root / "smairt.yaml").read_text()


def test_pdf_names_and_previewed_organizer_preserve_original(tmp_path: Path) -> None:
    root = project(tmp_path)
    original = tmp_path / "Downloaded Paper.pdf"
    original.write_bytes(pdf_bytes())
    record = add_reference(
        root,
        original,
        title="Über long human readable title for a carefully managed scientific paper",
        authors=["Ada Lovelace"],
        year=1843,
    )
    assert record.local_path
    assert Path(record.local_path).name == managed_pdf_filename(
        record.id, record.title, record.authors, record.year
    )
    managed = root / "references" / record.local_path
    legacy = root / "references/pdfs/legacy.pdf"
    managed.rename(legacy)
    record.local_path = "pdfs/legacy.pdf"
    save_index(root, [record])
    preview = organize_pdfs(root)
    assert preview["applied"] is False and preview["changes"]
    organize_pdfs(root, apply=True, confirmed=True)
    assert original.is_file()
    assert not legacy.exists()
    assert len(Path(load_index(root)[0].local_path or "").name.encode()) <= 120


def test_protected_literature_search_requires_confirm_remote(tmp_path: Path) -> None:
    """Gate discovery commands for private projects in both standard and strict modes."""
    root = tmp_path / "private-lit"
    create_project(
        root,
        name="Private Literature",
        author="Researcher",
        classification=DataClassification.PRIVATE,
        initialize_git=False,
        confirm_contributor=True,
    )
    with pytest.raises(ValueError, match="confirm-remote"):
        literature_search(root, "michaelis menten", confirm_remote=False)
    config = SmairtConfig.load(root / "smairt.yaml")
    config.safety_mode = SafetyMode.STRICT
    (root / "smairt.yaml").write_text(config.to_yaml())
    with pytest.raises(ValueError, match="confirm-remote"):
        literature_search(root, "michaelis menten", confirm_remote=False)
