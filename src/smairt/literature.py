"""Bounded literature discovery and explicit, SSRF-resistant open-access retrieval."""

from __future__ import annotations

import ipaddress
import json
import socket
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin, urlparse

import httpx
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from smairt import __version__
from smairt.credentials import CredentialError, resolve_credential
from smairt.errors import ExternalServiceError
from smairt.local_setup import resolve_profile
from smairt.locking import mutating
from smairt.models import AccessLocation, LiteratureCandidate, ReferenceRecord, utc_now
from smairt.references import (
    _require_remote_permission,
    get_reference,
    load_index,
    managed_pdf_filename,
    normalize_doi,
    render_index,
)
from smairt.transactions import FileTransaction

MAX_RESULTS = 50
MAX_PDF_BYTES = 100 * 1024 * 1024
MAX_REDIRECTS = 3


def _openalex_key(root: Path) -> str:
    """Resolve the checkout's user-local OpenAlex credential without exposing it."""
    _, profile = resolve_profile(root, "openalex")
    key, _ = resolve_credential(
        "openalex",
        profile.credential_profile,
        profile.environment_variable or "OPENALEX_API_KEY",
    )
    if not key:
        raise ValueError("OpenAlex API key is missing")
    return key


class OpenAlexProvider:
    """Expose bounded OpenAlex search and citation discovery."""

    def __init__(self, root: Path, *, client: httpx.Client | None = None) -> None:
        self.key = _openalex_key(root)
        self.client = client or httpx.Client(timeout=15, follow_redirects=False, trust_env=False)
        self.remaining_budget: str | float | None = None
        self.request_count = 0

    @staticmethod
    def _limit(limit: int) -> int:
        if limit < 1 or limit > MAX_RESULTS:
            raise ValueError(f"limit must be between 1 and {MAX_RESULTS}")
        return limit

    def _get(self, path: str, params: dict[str, object]) -> dict[str, Any]:
        response = self.client.get(
            f"https://api.openalex.org{path}",
            params={**dict[str, Any](params), "api_key": self.key},
            headers={"User-Agent": f"SMAIRT/{__version__}"},
        )
        self.request_count += 1
        self.remaining_budget = response.headers.get("X-RateLimit-Remaining")
        if response.status_code == 429:
            raise ExternalServiceError("OpenAlex rate limit is active")
        if response.status_code != 200:
            raise ExternalServiceError(f"OpenAlex request failed with HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise ExternalServiceError("OpenAlex returned malformed JSON") from exc
        if not isinstance(payload, dict):
            raise ExternalServiceError("OpenAlex returned an unexpected response")
        return payload

    def _candidates(self, payload: dict[str, Any]) -> list[LiteratureCandidate]:
        raw_results = payload.get("results")
        if not isinstance(raw_results, list):
            raise ExternalServiceError("OpenAlex response did not contain results")
        candidates: list[LiteratureCandidate] = []
        for raw in raw_results:
            if not isinstance(raw, dict) or not raw.get("id") or not raw.get("title"):
                continue
            authorships = raw.get("authorships") or []
            authors = [
                str(item.get("author", {}).get("display_name"))
                for item in authorships
                if isinstance(item, dict)
                and isinstance(item.get("author"), dict)
                and item["author"].get("display_name")
            ]
            ids_value = raw.get("ids")
            ids: dict[str, Any] = ids_value if isinstance(ids_value, dict) else {}
            doi_value = raw.get("doi") or ids.get("doi")
            doi = None
            if isinstance(doi_value, str):
                try:
                    doi = normalize_doi(doi_value)
                except ValueError:
                    doi = None
            location_value = raw.get("primary_location")
            location: dict[str, Any] = location_value if isinstance(location_value, dict) else {}
            source_value = location.get("source")
            source: dict[str, Any] = source_value if isinstance(source_value, dict) else {}
            candidates.append(
                LiteratureCandidate(
                    provider="openalex",
                    external_id=str(raw["id"]),
                    doi=doi,
                    title=str(raw["title"]),
                    authors=authors,
                    year=raw.get("publication_year")
                    if isinstance(raw.get("publication_year"), int)
                    else None,
                    venue=str(source.get("display_name")) if source.get("display_name") else None,
                    cited_by_count=raw.get("cited_by_count")
                    if isinstance(raw.get("cited_by_count"), int)
                    else None,
                    url=str(location.get("landing_page_url"))
                    if location.get("landing_page_url")
                    else None,
                    request_count=self.request_count,
                    remaining_budget=self.remaining_budget,
                )
            )
        return candidates

    def search(self, query: str, limit: int = 20) -> list[LiteratureCandidate]:
        """Search works without turning provisional results into project references."""
        if not query.strip() or len(query) > 500:
            raise ValueError("literature query must contain 1 to 500 characters")
        requested = self._limit(limit)
        return self._candidates(
            self._get("/works", {"search": query.strip(), "per-page": requested})
        )[:requested]

    def related(
        self, record: ReferenceRecord, direction: str, limit: int = 20
    ) -> list[LiteratureCandidate]:
        """Return works cited by, or citing, one DOI-backed reference."""
        if not record.doi:
            raise ValueError("citation discovery requires a DOI-backed reference")
        requested = self._limit(limit)
        work = self._get(f"/works/doi:{quote(record.doi, safe='')}", {})
        work_id = str(work.get("id") or "").rsplit("/", 1)[-1]
        if not work_id:
            raise ExternalServiceError("OpenAlex work lookup returned no identifier")
        if direction == "cited-by":
            params: dict[str, object] = {"filter": f"cites:{work_id}", "per-page": requested}
        elif direction == "references":
            references = work.get("referenced_works") or []
            ids = [str(value).rsplit("/", 1)[-1] for value in references[:requested]]
            if not ids:
                return []
            params = {"filter": "openalex_id:" + "|".join(ids), "per-page": requested}
        else:
            raise ValueError("direction must be references or cited-by")
        return self._candidates(self._get("/works", params))[:requested]


def _semantic_scholar_key(root: Path) -> str | None:
    """Resolve an optional Semantic Scholar key without requiring configuration."""
    import os

    if os.environ.get("SEMANTIC_SCHOLAR_API_KEY"):
        return os.environ["SEMANTIC_SCHOLAR_API_KEY"]
    try:
        _, profile = resolve_profile(root, "semantic_scholar")
        key, _ = resolve_credential(
            "semantic_scholar",
            profile.credential_profile,
            profile.environment_variable or "SEMANTIC_SCHOLAR_API_KEY",
        )
        return key
    except (CredentialError, ValueError):
        return None


class SemanticScholarProvider:
    """Expose bounded Semantic Scholar search, graph, and recommendations."""

    fields = "paperId,externalIds,title,authors,year,venue,citationCount,url,abstract"

    def __init__(self, root: Path, *, client: httpx.Client | None = None) -> None:
        self.key = _semantic_scholar_key(root)
        self.client = client or httpx.Client(timeout=15, follow_redirects=False, trust_env=False)
        self.request_count = 0

    @staticmethod
    def _limit(limit: int) -> int:
        if limit < 1 or limit > MAX_RESULTS:
            raise ValueError(f"limit must be between 1 and {MAX_RESULTS}")
        return limit

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, str | int] | None = None,
        payload: dict[str, object] | None = None,
    ) -> dict[str, Any]:
        headers = {"User-Agent": f"SMAIRT/{__version__}"}
        if self.key:
            headers["x-api-key"] = self.key
        response = self.client.request(method, url, params=params, json=payload, headers=headers)
        self.request_count += 1
        if response.status_code in {401, 403}:
            raise ExternalServiceError("Semantic Scholar rejected the configured API key")
        if response.status_code == 429:
            retry = response.headers.get("Retry-After")
            detail = f"; retry after {retry} seconds" if retry else ""
            raise ExternalServiceError(f"Semantic Scholar rate limit is active{detail}")
        if response.status_code == 404:
            raise ExternalServiceError("Semantic Scholar paper was not found")
        if response.status_code != 200:
            raise ExternalServiceError(
                f"Semantic Scholar request failed with HTTP {response.status_code}"
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise ExternalServiceError("Semantic Scholar returned malformed JSON") from exc
        if not isinstance(body, dict):
            raise ExternalServiceError("Semantic Scholar returned an unexpected response")
        return body

    def _candidates(self, values: object, *, method: str) -> list[LiteratureCandidate]:
        if not isinstance(values, list):
            raise ExternalServiceError("Semantic Scholar response did not contain results")
        candidates: list[LiteratureCandidate] = []
        for item in values:
            if not isinstance(item, dict):
                continue
            paper = item.get("citedPaper") or item.get("citingPaper") or item
            if not isinstance(paper, dict) or not paper.get("paperId") or not paper.get("title"):
                continue
            external = paper.get("externalIds")
            external_ids = external if isinstance(external, dict) else {}
            doi = None
            if external_ids.get("DOI"):
                try:
                    doi = normalize_doi(str(external_ids["DOI"]))
                except ValueError:
                    doi = None
            authors_value = paper.get("authors")
            raw_authors: list[Any] = authors_value if isinstance(authors_value, list) else []
            authors = [
                str(author["name"])
                for author in raw_authors
                if isinstance(author, dict) and author.get("name")
            ]
            candidates.append(
                LiteratureCandidate(
                    provider="semantic_scholar",
                    external_id=str(paper["paperId"]),
                    doi=doi,
                    title=str(paper["title"]),
                    authors=authors,
                    year=paper.get("year") if isinstance(paper.get("year"), int) else None,
                    venue=str(paper["venue"]) if paper.get("venue") else None,
                    cited_by_count=(
                        paper.get("citationCount")
                        if isinstance(paper.get("citationCount"), int)
                        else None
                    ),
                    url=str(paper["url"]) if paper.get("url") else None,
                    request_count=self.request_count,
                    discovery_method=method,
                    abstract_available=bool(paper.get("abstract")),
                )
            )
        return candidates

    def search(self, query: str, limit: int = 20) -> list[LiteratureCandidate]:
        """Return relevance-ranked provisional results."""
        if not query.strip() or len(query) > 500:
            raise ValueError("literature query must contain 1 to 500 characters")
        requested = self._limit(limit)
        body = self._request(
            "GET",
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params={"query": query.strip(), "limit": requested, "fields": self.fields},
        )
        return self._candidates(body.get("data"), method="search")[:requested]

    def related(
        self, record: ReferenceRecord, direction: str, limit: int = 20
    ) -> list[LiteratureCandidate]:
        """Return references or citations for one DOI-backed record."""
        if not record.doi:
            raise ValueError("citation discovery requires a DOI-backed reference")
        if direction not in {"references", "cited-by"}:
            raise ValueError("direction must be references or cited-by")
        requested = self._limit(limit)
        endpoint = "citations" if direction == "cited-by" else "references"
        paper_id = quote(record.doi, safe="")
        body = self._request(
            "GET",
            f"https://api.semanticscholar.org/graph/v1/paper/DOI:{paper_id}/{endpoint}",
            params={"limit": requested, "fields": self.fields},
        )
        return self._candidates(body.get("data"), method=direction)[:requested]

    def recommend(self, record: ReferenceRecord, limit: int = 20) -> list[LiteratureCandidate]:
        """Recommend papers from one DOI-backed positive seed."""
        if not record.doi:
            raise ValueError("recommendations require a DOI-backed reference")
        requested = self._limit(limit)
        body = self._request(
            "POST",
            "https://api.semanticscholar.org/recommendations/v1/papers/",
            params={"limit": requested, "fields": self.fields},
            payload={"positivePaperIds": [f"DOI:{record.doi}"], "negativePaperIds": []},
        )
        return self._candidates(body.get("recommendedPapers"), method="recommendation")[:requested]


class UnpaywallProvider:
    """Resolve one explicit DOI to a sanitized open-access location."""

    def __init__(self, root: Path, *, client: httpx.Client | None = None) -> None:
        _, profile = resolve_profile(root, "unpaywall")
        if not profile.contact_email:
            raise ValueError("Unpaywall contact email is missing")
        self.email = profile.contact_email
        self.client = client or httpx.Client(timeout=15, follow_redirects=False, trust_env=False)
        self.last_snapshot: dict[str, Any] | None = None

    def lookup(self, record: ReferenceRecord) -> AccessLocation:
        """Resolve access metadata without downloading or changing the project."""
        if not record.doi:
            raise ValueError("open-access lookup requires a DOI-backed reference")
        response = self.client.get(
            f"https://api.unpaywall.org/v2/{quote(normalize_doi(record.doi), safe='')}",
            params={"email": self.email},
            headers={"User-Agent": f"SMAIRT/{__version__}"},
        )
        if response.status_code == 404:
            raise ValueError("Unpaywall found no open-access location for this DOI")
        if response.status_code != 200:
            raise ExternalServiceError(f"Unpaywall request failed with HTTP {response.status_code}")
        try:
            raw = response.json()
        except ValueError as exc:
            raise ExternalServiceError("Unpaywall returned malformed JSON") from exc
        if not isinstance(raw, dict):
            raise ExternalServiceError("Unpaywall returned an unexpected response")
        location = raw.get("best_oa_location")
        if not isinstance(location, dict):
            raise ValueError("Unpaywall found no open-access location for this DOI")
        pdf_url = location.get("url_for_pdf")
        landing_url = location.get("url_for_landing_page") or location.get("url")
        selected = pdf_url or landing_url
        if not isinstance(selected, str) or not selected:
            raise ValueError("Unpaywall returned no usable access URL")
        host = urlparse(selected).hostname or ""
        self.last_snapshot = {
            "doi": raw.get("doi"),
            "is_oa": raw.get("is_oa"),
            "oa_status": raw.get("oa_status"),
            "best_oa_location": {
                key: location.get(key)
                for key in (
                    "url_for_pdf",
                    "url_for_landing_page",
                    "url",
                    "license",
                    "version",
                    "host_type",
                )
            },
        }
        return AccessLocation(
            reference_id=record.id,
            doi=normalize_doi(record.doi),
            url=selected,
            landing_url=str(landing_url) if landing_url else None,
            host=host,
            license=str(location.get("license")) if location.get("license") else None,
            version=str(location.get("version")) if location.get("version") else None,
            direct_pdf=bool(pdf_url),
        )


AddressResolver = Callable[..., list[tuple[Any, ...]]]


def _validate_download_url(url: str, resolver: AddressResolver) -> None:
    """Reject unsafe schemes, credentials, ports, and non-public resolved addresses."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("PDF downloads require an HTTPS URL")
    if parsed.username or parsed.password:
        raise ValueError("PDF download URLs cannot contain credentials")
    if parsed.port not in {None, 443}:
        raise ValueError("PDF download URLs must use port 443")
    try:
        addresses = resolver(parsed.hostname, 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ExternalServiceError("PDF host could not be resolved") from exc
    if not addresses:
        raise ExternalServiceError("PDF host resolved to no addresses")
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise ValueError("PDF host resolved to a private or reserved address")


def safe_download_pdf(
    url: str,
    *,
    client: httpx.Client | None = None,
    resolver: AddressResolver = socket.getaddrinfo,
) -> bytes:
    """Download and validate one bounded PDF with manual redirect checks."""
    owned_client = client is None
    session = client or httpx.Client(timeout=15, follow_redirects=False, trust_env=False)
    current = url
    try:
        for redirect_count in range(MAX_REDIRECTS + 1):
            _validate_download_url(current, resolver)
            request = session.build_request(
                "GET", current, headers={"User-Agent": f"SMAIRT/{__version__}"}
            )
            response = session.send(request, stream=True)
            try:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location or redirect_count == MAX_REDIRECTS:
                        raise ExternalServiceError("PDF download exceeded the redirect limit")
                    current = urljoin(current, location)
                    continue
                if response.status_code != 200:
                    raise ExternalServiceError(
                        f"PDF download failed with HTTP {response.status_code}"
                    )
                length = response.headers.get("content-length")
                if length and int(length) > MAX_PDF_BYTES:
                    raise ValueError("PDF download exceeds 100 MiB")
                content = bytearray()
                for chunk in response.iter_bytes():
                    content.extend(chunk)
                    if len(content) > MAX_PDF_BYTES:
                        raise ValueError("PDF download exceeds 100 MiB")
                data = bytes(content)
                if not data.startswith(b"%PDF-"):
                    raise ValueError("downloaded content does not contain a PDF signature")
                try:
                    import io

                    reader = PdfReader(io.BytesIO(data), strict=False)
                    if reader.is_encrypted:
                        raise ValueError("encrypted PDFs are not supported")
                    if not reader.pages:
                        raise ValueError("downloaded PDF contains no pages")
                except (PdfReadError, OSError) as exc:
                    raise ValueError("downloaded PDF is corrupt or unreadable") from exc
                return data
            finally:
                response.close()
    finally:
        if owned_client:
            session.close()
    raise ExternalServiceError("PDF download did not complete")


def literature_search(
    root: Path,
    query: str,
    limit: int = 20,
    provider: str = "openalex",
    *,
    confirm_remote: bool = False,
) -> list[LiteratureCandidate]:
    """Search one or both bounded discovery providers."""
    _require_remote_permission(root, confirm_remote)
    if provider == "openalex":
        return OpenAlexProvider(root).search(query, limit)
    if provider == "semantic-scholar":
        return SemanticScholarProvider(root).search(query, limit)
    if provider == "all":
        per_provider = max(1, min(MAX_RESULTS, limit))
        combined = OpenAlexProvider(root).search(query, per_provider)
        combined.extend(SemanticScholarProvider(root).search(query, per_provider))
        seen: set[str] = set()
        unique: list[LiteratureCandidate] = []
        for item in combined:
            identity = item.doi or f"{item.provider}:{item.external_id}"
            if identity not in seen:
                unique.append(item)
                seen.add(identity)
        return unique[:limit]
    raise ValueError("provider must be openalex, semantic-scholar, or all")


def literature_related(
    root: Path,
    identifier: str,
    direction: str,
    limit: int = 20,
    provider: str = "openalex",
    *,
    confirm_remote: bool = False,
) -> list[LiteratureCandidate]:
    """Discover bounded citation neighbors for one indexed reference."""
    _require_remote_permission(root, confirm_remote)
    record = get_reference(root, identifier)
    if provider == "openalex":
        return OpenAlexProvider(root).related(record, direction, limit)
    if provider == "semantic-scholar":
        return SemanticScholarProvider(root).related(record, direction, limit)
    raise ValueError("provider must be openalex or semantic-scholar")


def literature_recommend(
    root: Path,
    identifier: str,
    limit: int = 20,
    *,
    confirm_remote: bool = False,
) -> list[LiteratureCandidate]:
    """Recommend provisional Semantic Scholar candidates from one project reference."""
    _require_remote_permission(root, confirm_remote)
    return SemanticScholarProvider(root).recommend(get_reference(root, identifier), limit)


@mutating("literature open-access download")
def literature_access(
    root: Path,
    identifier: str,
    *,
    download: bool = False,
    confirmed: bool = False,
    confirm_remote: bool = False,
    download_client: httpx.Client | None = None,
    resolver: AddressResolver = socket.getaddrinfo,
) -> dict[str, object]:
    """Resolve OA metadata and optionally attach one validated managed PDF atomically."""
    _require_remote_permission(root, confirm_remote)
    records = load_index(root)
    record = next((item for item in records if item.id == identifier), None)
    if record is None:
        raise ValueError(f"unknown reference: {identifier}")
    provider = UnpaywallProvider(root)
    location = provider.lookup(record)
    result: dict[str, object] = {
        "location": location.model_dump(mode="json", exclude_none=True),
        "downloaded": False,
        "provider": "unpaywall",
        "network_accessed": True,
        "request_count": 1,
    }
    if not download:
        return result
    if not confirmed:
        raise ValueError("open-access PDF download requires --yes")
    if not location.direct_pdf:
        return result
    if record.local_path:
        raise ValueError("reference already has an attached PDF")
    content = safe_download_pdf(location.url, client=download_client, resolver=resolver)
    import hashlib

    digest = hashlib.sha256(content).hexdigest()
    if any(item.sha256 == digest for item in records):
        raise ValueError("this PDF is already indexed")
    destination = (
        root
        / "references/pdfs"
        / managed_pdf_filename(record.id, record.title, record.authors, record.year)
    )
    if destination.exists():
        raise ValueError("managed PDF destination already exists")
    position = records.index(record)
    payload = record.model_dump(mode="json", exclude_none=True)
    payload.update(local_path=str(destination.relative_to(root / "references")), sha256=digest)
    record = ReferenceRecord.model_validate(payload)
    records[position] = record
    captured = utc_now()
    snapshot = (
        root / "references/provenance" / record.id / f"unpaywall-{captured.replace(':', '')}.json"
    )
    record.source_provenance.extend(
        [
            {
                "source": "unpaywall",
                "captured_at": captured,
                "snapshot": str(snapshot.relative_to(root)),
            },
            {
                "source": "open_access_pdf",
                "captured_at": captured,
                "sha256": digest,
                "original_filename": Path(urlparse(location.url).path).name or "download.pdf",
            },
        ]
    )
    transaction = FileTransaction(root, "literature open-access download")
    transaction.stage_text(
        snapshot, json.dumps(provider.last_snapshot or {}, indent=2, sort_keys=True) + "\n"
    )
    transaction.stage_bytes(destination, content, mode=0o644)
    transaction.stage_text(root / "references/index.yaml", render_index(records))
    transaction.commit()
    result.update(downloaded=True, local_path=record.local_path, sha256=digest)
    return result
