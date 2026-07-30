"""Local reference-library indexing with explicit human metadata verification."""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import yaml
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from smairt import __version__
from smairt.errors import ExternalServiceError
from smairt.locking import mutating
from smairt.models import ReferenceRecord, SmairtConfig, VerificationStatus, utc_now
from smairt.transactions import FileTransaction
from smairt.utils import (
    atomic_write,
    ensure_within,
    sha256_file,
    sha256_text,
    slugify,
    validate_identifier,
)

DOI_PATTERN = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
MAX_METADATA_BYTES = 10 * 1024 * 1024


class CrossrefNotFoundError(ExternalServiceError):
    """Indicate the only Crossref failure that permits a DataCite fallback."""


def managed_pdf_filename(identifier: str, title: str, authors: list[str], year: int | None) -> str:
    """Return a deterministic, human-readable, collision-resistant managed PDF name."""
    author = authors[0].split()[-1] if authors and authors[0].split() else "anon"
    title_words = re.findall(r"[A-Za-z0-9]+", title)[:8]
    title_slug = slugify("-".join(title_words) or "untitled")
    stable = hashlib.sha256(identifier.encode("utf-8")).hexdigest()[:8]
    prefix = slugify(f"{author}-{year or 'nd'}-{title_slug}")
    maximum_prefix = 120 - len(stable) - len("-.pdf")
    return f"{prefix[:maximum_prefix].rstrip('-')}-{stable}.pdf"


def render_index(records: list[ReferenceRecord]) -> str:
    """Render a validated deterministic reference index for atomic transactions."""
    payload = {
        "schema_version": 2,
        "references": [record.model_dump(mode="json", exclude_none=True) for record in records],
    }
    return yaml.safe_dump(payload, sort_keys=False)


_index_yaml = render_index


def normalize_doi(value: str) -> str:
    """Normalize and validate DOI strings from common URL and label forms."""
    normalized = value.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        normalized = normalized.removeprefix(prefix)
    if not DOI_PATTERN.fullmatch(normalized):
        raise ValueError(f"invalid DOI: {value}")
    return normalized


def _read_metadata_response(response: Any, service: str) -> object:
    """Decode one bounded metadata response without trusting server size claims."""
    headers = getattr(response, "headers", None)
    length = headers.get("Content-Length") if headers is not None else None
    if length is not None:
        try:
            if int(length) > MAX_METADATA_BYTES:
                raise ExternalServiceError(f"{service} response exceeded the size limit")
        except ValueError as exc:
            raise ExternalServiceError(f"{service} returned an invalid Content-Length") from exc
    try:
        body = response.read(MAX_METADATA_BYTES + 1)
    except TypeError:  # Simple test doubles and older file-like implementations.
        body = response.read()
    if not isinstance(body, bytes) or len(body) > MAX_METADATA_BYTES:
        raise ExternalServiceError(f"{service} response exceeded the size limit")
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise ExternalServiceError(f"{service} returned malformed JSON") from exc


def _first_string(value: object, fallback: str | None = None) -> str | None:
    """Return a scalar or first-list string from a metadata service field."""
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value and isinstance(value[0], str):
        return value[0]
    return fallback


def load_index(root: Path) -> list[ReferenceRecord]:
    """Load and validate all reference records from the project index."""
    payload = yaml.safe_load((root / "references/index.yaml").read_text(encoding="utf-8")) or {}
    version = payload.get("schema_version", 1)
    if version not in {1, 2}:
        raise ValueError("unsupported reference index schema")
    return [ReferenceRecord.model_validate(item) for item in payload.get("references", [])]


def doi_reference_id(doi: str) -> str:
    """Return a stable opaque ID for a normalized DOI."""
    return f"doi-{sha256_text(normalize_doi(doi))[:20]}"


def zotero_reference_id(library_type: str, item_key: str) -> str:
    """Return a stable path-safe ID for a Zotero-only item."""
    if library_type not in {"user", "group"}:
        raise ValueError("Zotero library type must be user or group")
    key = validate_identifier(item_key, label="Zotero item key")
    return f"zotero-{library_type}-{key.lower()}"


@mutating("reference index save")
def save_index(root: Path, records: list[ReferenceRecord]) -> None:
    """Persist validated reference records in a stable YAML representation."""
    atomic_write(root / "references/index.yaml", _index_yaml(records))


def inspect_pdf(source: Path) -> dict[str, Any]:
    """Extract best-effort PDF metadata for explicit researcher confirmation."""
    if source.stat().st_size == 0:
        raise ValueError("PDF is empty")
    if source.stat().st_size > 100 * 1024 * 1024:
        raise ValueError("PDF exceeds the 100 MiB local inspection limit")
    try:
        reader = PdfReader(str(source), strict=False)
    except (PdfReadError, OSError) as exc:
        raise ValueError("PDF is corrupt or unreadable") from exc
    if reader.is_encrypted:
        raise ValueError("encrypted PDFs are not supported")
    if not reader.pages:
        raise ValueError("PDF contains no pages")
    metadata: Any = reader.metadata or {}
    title = str(metadata.get("/Title") or source.stem).strip()
    author = str(metadata.get("/Author") or "").strip()
    text = "\n".join((page.extract_text() or "")[:5000] for page in reader.pages[:5])
    match = DOI_PATTERN.search(text)
    return {
        "title": title,
        "authors": [item.strip() for item in author.split(";") if item.strip()],
        "doi": match.group(0).rstrip(".,;)") if match else None,
        "pages": len(reader.pages),
    }


@mutating("reference add")
def add_reference(
    root: Path,
    source: Path,
    *,
    title: str,
    authors: list[str] | None = None,
    year: int | None = None,
    doi: str | None = None,
    link: bool = False,
) -> ReferenceRecord:
    """Copy a PDF and append unverified metadata through one transaction."""
    root = root.resolve()
    source = source.expanduser().absolute()
    if source.is_symlink() or any(parent.is_symlink() for parent in source.parents):
        raise ValueError("reference source must not traverse a symlink")
    source = source.resolve()
    if source.suffix.lower() != ".pdf" or not source.exists():
        raise ValueError("reference must be an existing PDF")
    if link:
        raise ValueError("linked references are not supported by the recoverable beta index")
    records = load_index(root)
    digest = sha256_file(source)
    if any(record.sha256 == digest for record in records):
        raise ValueError("this PDF is already indexed")
    record_id = slugify(f"{year or 'undated'}-{title}")[:80]
    destination = (
        root / "references/pdfs" / managed_pdf_filename(record_id, title, authors or [], year)
    )
    ensure_within(root, destination)
    parent = destination.parent
    while parent != root.resolve():
        if parent.is_symlink():
            raise ValueError("reference destination must not traverse a symlink")
        parent = parent.parent
    citation_key = (
        slugify(f"{(authors or ['anon'])[0].split()[-1]}-{year or 'nd'}-{title.split()[0]}")
        if title.split()
        else record_id
    )
    normalized_doi = normalize_doi(doi) if doi else None
    if any(item.id == record_id for item in records):
        raise ValueError(f"duplicate reference ID: {record_id}")
    if any(item.citation_key == citation_key for item in records):
        raise ValueError(f"duplicate citation key: {citation_key}")
    if normalized_doi and any(item.doi == normalized_doi for item in records):
        raise ValueError(f"duplicate DOI: {normalized_doi}")
    if os.path.lexists(destination):
        raise ValueError(f"reference destination already exists: {destination.name}")
    record = ReferenceRecord(
        id=record_id,
        title=title,
        authors=authors or [],
        year=year,
        doi=normalized_doi,
        local_path=str(destination.relative_to(root / "references")),
        sha256=digest,
        metadata_verified=False,
        citation_key=citation_key,
        identifiers={"doi": normalized_doi} if normalized_doi else {},
        verification_status=VerificationStatus.UNVERIFIED,
        source_provenance=[
            {
                "source": "local_pdf",
                "captured_at": utc_now(),
                "sha256": digest,
                "original_filename": source.name,
            }
        ],
    )
    records.append(record)
    transaction = FileTransaction(root, "reference add")
    transaction.stage_bytes(destination, source.read_bytes(), mode=0o644)
    transaction.stage_text(root / "references/index.yaml", _index_yaml(records))
    transaction.commit()
    return record


def _fetch_crossref(doi: str) -> dict[str, Any]:
    """Fetch one bounded Crossref work record."""
    url = "https://api.crossref.org/works/" + urllib.parse.quote(normalize_doi(doi))
    request = urllib.request.Request(  # noqa: S310
        url, headers={"User-Agent": f"SMAIRT/{__version__}"}
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310
            if getattr(response, "status", 200) != 200:
                raise ExternalServiceError("Crossref returned an unsuccessful response")
            raw = _read_metadata_response(response, "Crossref")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise CrossrefNotFoundError("Crossref has no record for this DOI") from None
        raise ExternalServiceError(f"Crossref request failed with HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError):
        raise ExternalServiceError("Crossref is unavailable; no reference was changed") from None
    if not isinstance(raw, dict) or not isinstance(raw.get("message"), dict):
        raise ExternalServiceError("Crossref returned an unexpected record shape")
    return raw


def _fetch_datacite(doi: str) -> dict[str, Any]:
    """Fetch one bounded public DataCite DOI record after a Crossref 404."""
    url = "https://api.datacite.org/dois/" + urllib.parse.quote(normalize_doi(doi))
    request = urllib.request.Request(  # noqa: S310 - fixed HTTPS endpoint
        url, headers={"User-Agent": f"SMAIRT/{__version__}"}
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310
            if getattr(response, "status", 200) != 200:
                raise ExternalServiceError("DataCite returned an unsuccessful response")
            raw = _read_metadata_response(response, "DataCite")
    except urllib.error.HTTPError as exc:
        raise ExternalServiceError(f"DataCite request failed with HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError):
        raise ExternalServiceError("DataCite is unavailable; no reference was changed") from None
    if not isinstance(raw, dict) or not isinstance(raw.get("data"), dict):
        raise ExternalServiceError("DataCite returned an unexpected record shape")
    attributes = raw["data"].get("attributes")
    if not isinstance(attributes, dict):
        raise ExternalServiceError("DataCite returned malformed DOI attributes")
    return raw


def _merge_datacite(record: ReferenceRecord, raw: dict[str, Any]) -> None:
    """Fill missing, unverified fields from a validated DataCite record."""
    attributes = raw["data"]["attributes"]
    titles = attributes.get("titles") or []
    creators = attributes.get("creators") or []
    dates = attributes.get("dates") or []
    title = titles[0].get("title") if titles and isinstance(titles[0], dict) else None
    authors = [
        str(
            item.get("name")
            or " ".join(filter(None, [item.get("givenName"), item.get("familyName")]))
        )
        for item in creators
        if isinstance(item, dict)
    ]
    year = attributes.get("publicationYear")
    publication_date = next(
        (
            item.get("date")
            for item in dates
            if isinstance(item, dict) and item.get("dateType") in {"Issued", "Published"}
        ),
        None,
    )
    values: dict[str, Any] = {
        "title": title,
        "authors": [item for item in authors if item],
        "year": year,
        "publication_date": publication_date,
        "publisher": attributes.get("publisher"),
        "url": attributes.get("url"),
    }
    edited = {str(item.get("field")) for item in record.edit_history}
    for field, value in values.items():
        fill_empty = value is not None and value != [] and not getattr(record, field)
        replace_seed = record.verification_status is not VerificationStatus.VERIFIED and field in {
            "title",
            "authors",
        }
        if value and field not in edited and (fill_empty or replace_seed):
            setattr(record, field, value)


def _merge_crossref(record: ReferenceRecord, raw: dict[str, Any]) -> None:
    """Fill missing fields without overwriting verified or manually edited metadata."""
    message = raw["message"]
    authors = message.get("author", [])
    if not isinstance(authors, list) or not all(isinstance(author, dict) for author in authors):
        raise ExternalServiceError("Crossref returned malformed author metadata")
    values: dict[str, Any] = {
        "title": _first_string(message.get("title")),
        "authors": [
            " ".join(
                part
                for part in (author.get("given"), author.get("family"))
                if isinstance(part, str) and part
            )
            for author in authors
        ],
        "venue": _first_string(message.get("container-title")),
        "volume": message.get("volume"),
        "issue": message.get("issue"),
        "pages": message.get("page"),
        "publisher": message.get("publisher"),
        "url": message.get("URL"),
    }
    date_parts = (message.get("published-print") or message.get("published") or {}).get(
        "date-parts", []
    )
    if date_parts and isinstance(date_parts[0], list) and date_parts[0]:
        values["year"] = date_parts[0][0]
    edited = {str(item.get("field")) for item in record.edit_history}
    for field, value in values.items():
        fill_empty = value is not None and value != [] and not getattr(record, field)
        replace_seed = record.verification_status is not VerificationStatus.VERIFIED and field in {
            "title",
            "authors",
        }
        if value and field not in edited and (fill_empty or replace_seed):
            setattr(record, field, value)


def _resolve_openalex_key(root: Path, api_key: str | None = None) -> str:
    """Resolve the configured OpenAlex profile without exposing the credential."""
    if api_key:
        return api_key
    from smairt.credentials import resolve_credential

    config = SmairtConfig.load(root / "smairt.yaml")
    try:
        from smairt.local_setup import resolve_profile

        _, local_profile = resolve_profile(root, "openalex")
        profile_name = local_profile.credential_profile
        environment_variable = local_profile.environment_variable or "OPENALEX_API_KEY"
    except ValueError:
        if config.schema_version >= 5:
            raise
        profile = config.integrations.openalex.credential
        profile_name = profile.profile
        environment_variable = profile.environment_variable or "OPENALEX_API_KEY"
    key, _ = resolve_credential("openalex", profile_name, environment_variable)
    if not key:
        raise ValueError("OpenAlex credential is missing")
    return key


def _fetch_openalex(doi: str, api_key: str) -> dict[str, Any]:
    """Fetch and validate one bounded OpenAlex work response."""
    external_id = urllib.parse.quote(f"doi:{normalize_doi(doi)}", safe=":")
    url = f"https://api.openalex.org/works/{external_id}?" + urllib.parse.urlencode(
        {"api_key": api_key}
    )
    request = urllib.request.Request(  # noqa: S310 - fixed HTTPS endpoint
        url, headers={"User-Agent": f"SMAIRT/{__version__}"}
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310
            if getattr(response, "status", 200) != 200:
                raise ExternalServiceError("OpenAlex returned an unsuccessful response")
            raw = _read_metadata_response(response, "OpenAlex")
    except urllib.error.HTTPError as exc:
        raise ExternalServiceError(f"OpenAlex request failed with HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError):
        raise ExternalServiceError("OpenAlex is unavailable; no reference was changed") from None
    if not isinstance(raw, dict) or not raw.get("id"):
        raise ExternalServiceError("OpenAlex returned an unexpected or empty record")
    location = raw.get("primary_location") or {}
    if not isinstance(location, dict) or not isinstance(location.get("source") or {}, dict):
        raise ExternalServiceError("OpenAlex returned malformed location metadata")
    return raw


def _merge_openalex(record: ReferenceRecord, raw: dict[str, Any]) -> None:
    """Supplement only missing, non-manually-edited fields from OpenAlex."""
    location = raw.get("primary_location") or {}
    source = location.get("source") or {}
    edited = {str(item.get("field")) for item in record.edit_history}
    values = {
        "publication_date": raw.get("publication_date"),
        "venue": source.get("display_name"),
        "url": location.get("landing_page_url"),
        "license": location.get("license"),
    }
    for field, value in values.items():
        if value and not getattr(record, field) and field not in edited:
            setattr(record, field, value)
    record.identifiers.setdefault("openalex", str(raw["id"]))


@mutating("reference add DOI")
def add_doi_reference(
    root: Path,
    doi: str,
    *,
    use_openalex: bool = False,
    confirm_remote: bool = False,
) -> ReferenceRecord:
    """Create or merge one metadata-only DOI record from Crossref."""
    _require_remote_permission(root, confirm_remote)
    normalized = normalize_doi(doi)
    provider_name = "crossref"
    try:
        authority_raw = _fetch_crossref(normalized)
    except CrossrefNotFoundError:
        provider_name = "datacite"
        authority_raw = _fetch_datacite(normalized)
    openalex_raw = None
    if use_openalex:
        openalex_raw = _fetch_openalex(normalized, _resolve_openalex_key(root))
    records = load_index(root)
    record = next((item for item in records if item.doi == normalized), None)
    if record is None:
        record = ReferenceRecord(
            id=doi_reference_id(normalized),
            title=normalized,
            doi=normalized,
            identifiers={"doi": normalized},
        )
        records.append(record)
    if provider_name == "crossref":
        _merge_crossref(record, authority_raw)
    else:
        _merge_datacite(record, authority_raw)
    if openalex_raw is not None:
        _merge_openalex(record, openalex_raw)
    captured = utc_now()
    authority_snapshot = (
        root
        / "references/provenance"
        / record.id
        / f"{provider_name}-{captured.replace(':', '')}.json"
    )
    record.source_provenance.append(
        {
            "source": provider_name,
            "captured_at": captured,
            "snapshot": str(authority_snapshot.relative_to(root)),
        }
    )
    openalex_snapshot = None
    if openalex_raw is not None:
        openalex_snapshot = (
            root
            / "references/provenance"
            / record.id
            / f"openalex-{captured.replace(':', '')}.json"
        )
        record.source_provenance.append(
            {
                "source": "openalex",
                "captured_at": captured,
                "snapshot": str(openalex_snapshot.relative_to(root)),
            }
        )
    if record.verification_status is not VerificationStatus.VERIFIED:
        record.verification_status = VerificationStatus.ENRICHED_UNVERIFIED
    transaction = FileTransaction(root, "reference add DOI")
    transaction.stage_text(
        authority_snapshot, json.dumps(authority_raw, indent=2, sort_keys=True) + "\n"
    )
    if openalex_raw is not None and openalex_snapshot is not None:
        transaction.stage_text(
            openalex_snapshot, json.dumps(openalex_raw, indent=2, sort_keys=True) + "\n"
        )
    transaction.stage_text(root / "references/index.yaml", _index_yaml(records))
    transaction.commit()
    return record


@mutating("reference attach")
def attach_reference(root: Path, identifier: str, source: Path) -> ReferenceRecord:
    """Attach one explicitly selected local PDF to a metadata-only record."""
    source = source.expanduser().absolute()
    if (
        source.is_symlink()
        or any(parent.is_symlink() for parent in source.parents)
        or not source.exists()
        or source.suffix.lower() != ".pdf"
    ):
        raise ValueError("attachment must be an existing non-symlink PDF")
    source = source.resolve()
    inspect_pdf(source)
    records = load_index(root)
    record = next((item for item in records if item.id == identifier), None)
    if record is None:
        raise ValueError(f"unknown reference: {identifier}")
    if record.local_path:
        raise ValueError("reference already has an attachment")
    digest = sha256_file(source)
    if any(item.sha256 == digest for item in records):
        raise ValueError("this PDF is already indexed")
    destination = (
        root
        / "references/pdfs"
        / managed_pdf_filename(record.id, record.title, record.authors, record.year)
    )
    ensure_within(root, destination)
    if os.path.lexists(destination):
        raise ValueError("reference attachment destination already exists")
    position = records.index(record)
    payload = record.model_dump(mode="json", exclude_none=True)
    payload.update(local_path=str(destination.relative_to(root / "references")), sha256=digest)
    record = ReferenceRecord.model_validate(payload)
    records[position] = record
    record.source_provenance.append(
        {
            "source": "local_pdf",
            "captured_at": utc_now(),
            "sha256": digest,
            "original_filename": source.name,
        }
    )
    transaction = FileTransaction(root, "reference attach")
    transaction.stage_bytes(destination, source.read_bytes(), mode=0o644)
    transaction.stage_text(root / "references/index.yaml", _index_yaml(records))
    transaction.commit()
    return record


@mutating("reference organize PDFs")
def organize_pdfs(root: Path, *, apply: bool = False, confirmed: bool = False) -> dict[str, object]:
    """Preview or atomically apply deterministic names to managed reference copies."""
    if apply and not confirmed:
        raise ValueError("applying PDF organization requires --yes")
    records = load_index(root)
    changes: list[dict[str, str]] = []
    moves: list[tuple[ReferenceRecord, Path, Path]] = []
    for record in records:
        if not record.local_path or not record.sha256:
            continue
        source = ensure_within(root, root / "references" / record.local_path)
        if not source.is_file() or sha256_file(source) != record.sha256:
            raise ValueError(f"managed PDF checksum mismatch: {record.id}")
        destination = (
            root
            / "references/pdfs"
            / managed_pdf_filename(record.id, record.title, record.authors, record.year)
        )
        ensure_within(root, destination)
        if source == destination:
            continue
        if os.path.lexists(destination):
            raise ValueError(f"managed PDF destination already exists: {destination.name}")
        changes.append(
            {
                "reference": record.id,
                "from": str(source.relative_to(root)),
                "to": str(destination.relative_to(root)),
            }
        )
        moves.append((record, source, destination))
    result: dict[str, object] = {"applied": apply, "changes": changes}
    if not apply or not moves:
        return result
    transaction = FileTransaction(root, "reference organize PDFs")
    for record, source, destination in moves:
        transaction.stage_bytes(destination, source.read_bytes(), mode=0o644)
        transaction.stage_delete(source)
        record.local_path = str(destination.relative_to(root / "references"))
    transaction.stage_text(root / "references/index.yaml", _index_yaml(records))
    transaction.commit()
    return result


def _merge_zotero_item(
    records: list[ReferenceRecord], provider: Any, raw: dict[str, Any], fallback_key: str
) -> ReferenceRecord:
    """Merge one already-fetched Zotero record without changing a stable ID."""
    from smairt.zotero import public_item

    item = public_item(raw)
    doi_value = item.get("DOI")
    doi = normalize_doi(str(doi_value)) if doi_value else None
    record = next((existing for existing in records if doi and existing.doi == doi), None)
    key = str(item.get("key") or fallback_key)
    validate_identifier(key, label="Zotero item key")
    creators = item.get("creators") or []
    authors = [
        str(
            creator.get("name")
            or " ".join(
                part for part in (creator.get("firstName"), creator.get("lastName")) if part
            )
        )
        for creator in creators
        if isinstance(creator, dict)
    ]
    date = str(item.get("date") or "")
    year_match = re.search(r"\b(\d{4})\b", date)
    if record is None:
        record = ReferenceRecord(
            id=doi_reference_id(doi)
            if doi
            else zotero_reference_id(provider.config.library_type.value, key),
            title=str(item.get("title") or f"Zotero item {key}"),
            authors=[author for author in authors if author],
            year=int(year_match.group(1)) if year_match else None,
            doi=doi,
            venue=str(item.get("publicationTitle") or "") or None,
            url=str(item.get("url") or "") or None,
            identifiers={"zotero": key, **({"doi": doi} if doi else {})},
        )
        records.append(record)
    else:
        record.identifiers.setdefault("zotero", key)
        edited = {str(entry.get("field")) for entry in record.edit_history}
        missing: dict[str, Any] = {
            "authors": [author for author in authors if author],
            "year": int(year_match.group(1)) if year_match else None,
            "venue": str(item.get("publicationTitle") or "") or None,
            "url": str(item.get("url") or "") or None,
        }
        for field, value in missing.items():
            if value and not getattr(record, field) and field not in edited:
                setattr(record, field, value)
    return record


def _zotero_snapshot(root: Path, record: ReferenceRecord, captured: str, suffix: str) -> Path:
    """Return one collision-resistant bounded raw-snapshot location."""
    safe_suffix = validate_identifier(suffix, label="Zotero item key").lower()
    stamp = captured.replace(":", "").replace("+", "")
    return root / "references/provenance" / record.id / f"zotero-{stamp}-{safe_suffix}.json"


@mutating("reference import Zotero")
def import_zotero_item(root: Path, item_key: str) -> ReferenceRecord:
    """Import one Zotero item as metadata in one recoverable transaction."""
    from smairt.zotero import ZoteroProvider, public_item

    provider = ZoteroProvider(root)
    raw = provider.item(item_key)
    records = load_index(root)
    record = _merge_zotero_item(records, provider, raw, item_key)
    captured = utc_now()
    snapshot = _zotero_snapshot(root, record, captured, item_key)
    record.source_provenance.append(
        {"source": "zotero", "captured_at": captured, "snapshot": str(snapshot.relative_to(root))}
    )
    transaction = FileTransaction(root, "reference import Zotero")
    transaction.stage_text(snapshot, json.dumps(public_item(raw), indent=2, sort_keys=True) + "\n")
    transaction.stage_text(root / "references/index.yaml", _index_yaml(records))
    transaction.commit()
    return record


@mutating("reference import Zotero collection")
def import_zotero_collection(
    root: Path, collection_key: str, *, limit: int = 500
) -> list[ReferenceRecord]:
    """Import one paginated collection atomically without per-item refetches."""
    from smairt.zotero import ZoteroProvider, public_item

    provider = ZoteroProvider(root)
    raw_items = provider.collection_items(collection_key, limit)
    records = load_index(root)
    imported: list[ReferenceRecord] = []
    snapshots: list[tuple[Path, dict[str, Any]]] = []
    for raw in raw_items:
        data_value = raw.get("data")
        data = data_value if isinstance(data_value, dict) else {}
        key_value = raw.get("key") or data.get("key")
        if not isinstance(key_value, str) or not key_value:
            raise ValueError("Zotero collection contained an item without a key")
        record = _merge_zotero_item(records, provider, raw, key_value)
        captured = utc_now()
        snapshot = _zotero_snapshot(root, record, captured, key_value)
        record.source_provenance.append(
            {
                "source": "zotero",
                "captured_at": captured,
                "snapshot": str(snapshot.relative_to(root)),
            }
        )
        snapshots.append((snapshot, public_item(raw)))
        if record not in imported:
            imported.append(record)
    transaction = FileTransaction(root, "reference import Zotero collection")
    for snapshot, raw in snapshots:
        transaction.stage_text(snapshot, json.dumps(raw, indent=2, sort_keys=True) + "\n")
    transaction.stage_text(root / "references/index.yaml", _index_yaml(records))
    transaction.commit()
    return imported


def copy_zotero_attachment(
    root: Path, item_key: str, attachment_key: str, *, confirmed: bool
) -> ReferenceRecord:
    """Copy one explicitly selected local Zotero PDF attachment."""
    from smairt.models import ZoteroMode
    from smairt.zotero import ZoteroProvider, public_item

    if not confirmed:
        raise ValueError("local Zotero attachment copying requires --yes")
    provider = ZoteroProvider(root)
    if provider.config.mode is not ZoteroMode.LOCAL:
        raise ValueError("Web attachment downloads are out of scope")
    parent_raw = provider.item(item_key)
    child = next(
        (
            item
            for item in provider.children(item_key)
            if str(item.get("key") or item.get("data", {}).get("key")) == attachment_key
        ),
        None,
    )
    if child is None:
        raise ValueError("unknown Zotero attachment")
    attachment_raw, content = provider.local_attachment(attachment_key)
    try:
        reader = PdfReader(io.BytesIO(content), strict=False)
        if reader.is_encrypted:
            raise ValueError("encrypted PDFs are not supported")
        if not reader.pages:
            raise ValueError("PDF contains no pages")
    except (PdfReadError, OSError) as exc:
        raise ValueError("Zotero attachment is corrupt or unreadable") from exc

    records = load_index(root)
    record = _merge_zotero_item(records, provider, parent_raw, item_key)
    if record.local_path:
        raise ValueError("reference already has an attachment")
    digest = hashlib.sha256(content).hexdigest()
    if any(existing.sha256 == digest for existing in records):
        raise ValueError("this PDF is already indexed")
    destination = (
        root
        / "references/pdfs"
        / managed_pdf_filename(record.id, record.title, record.authors, record.year)
    )
    ensure_within(root, destination)
    if os.path.lexists(destination):
        raise ValueError("reference attachment destination already exists")
    position = records.index(record)
    payload = record.model_dump(mode="json", exclude_none=True)
    payload.update(local_path=str(destination.relative_to(root / "references")), sha256=digest)
    record = ReferenceRecord.model_validate(payload)
    records[position] = record
    captured = utc_now()
    parent_snapshot = _zotero_snapshot(root, record, captured, item_key)
    attachment_snapshot = _zotero_snapshot(root, record, captured, attachment_key)
    record.source_provenance.extend(
        [
            {
                "source": "zotero",
                "captured_at": captured,
                "snapshot": str(parent_snapshot.relative_to(root)),
            },
            {"source": "zotero_local_pdf", "captured_at": captured, "sha256": digest},
        ]
    )
    transaction = FileTransaction(root, "reference copy Zotero attachment")
    transaction.stage_text(
        parent_snapshot, json.dumps(public_item(parent_raw), indent=2, sort_keys=True) + "\n"
    )
    transaction.stage_text(
        attachment_snapshot,
        json.dumps(public_item(attachment_raw), indent=2, sort_keys=True) + "\n",
    )
    transaction.stage_bytes(destination, content, mode=0o644)
    transaction.stage_text(root / "references/index.yaml", _index_yaml(records))
    transaction.commit()
    return record


def get_reference(root: Path, identifier: str) -> ReferenceRecord:
    """Return one indexed reference by stable identifier."""
    validate_identifier(identifier, label="reference ID")
    record = next((item for item in load_index(root) if item.id == identifier), None)
    if record is None:
        raise ValueError(f"unknown reference: {identifier}")
    return record


@mutating("reference edit")
def edit_reference(
    root: Path, identifier: str, field: str, value: str, contributor: str
) -> ReferenceRecord:
    """Edit an allowed metadata field and append field-level provenance."""
    records = load_index(root)
    record = next((item for item in records if item.id == identifier), None)
    if record is None:
        raise ValueError(f"unknown reference: {identifier}")
    if field not in ReferenceRecord.model_fields or field in {"id", "sha256", "local_path"}:
        raise ValueError(f"field cannot be edited: {field}")
    previous = getattr(record, field)
    if field == "doi":
        value = normalize_doi(value)
    parsed: object
    if field == "year":
        parsed = int(value)
    elif field == "authors":
        parsed = [item.strip() for item in value.split(",") if item.strip()]
        if not parsed:
            raise ValueError("authors must contain at least one name")
    else:
        parsed = value
    setattr(record, field, parsed)
    record.edit_history.append(
        {
            "field": field,
            "previous": previous,
            "value": parsed,
            "contributor": contributor,
            "edited_at": utc_now(),
        }
    )
    record.verification_status = VerificationStatus.UNVERIFIED
    record.metadata_verified = False
    save_index(root, records)
    return record


@mutating("reference verify")
def verify_reference(root: Path, identifier: str, contributor: str) -> ReferenceRecord:
    """Validate required metadata, DOI, pages, and duplicates before verification."""
    records = load_index(root)
    record = next((item for item in records if item.id == identifier), None)
    if record is None:
        raise ValueError(f"unknown reference: {identifier}")
    if not record.title.strip() or not record.authors:
        raise ValueError("reference requires title and authors before verification")
    if record.doi:
        record.doi = normalize_doi(record.doi)
    if record.pages and not re.fullmatch(r"[A-Za-z]?\d+(?:[-\u2013][A-Za-z]?\d+)?", record.pages):
        raise ValueError("invalid page range")
    duplicate_keys = [
        r.id for r in records if r.id != record.id and r.citation_key == record.citation_key
    ]
    duplicate_dois = [
        r.id for r in records if r.id != record.id and record.doi and r.doi == record.doi
    ]
    if duplicate_keys or duplicate_dois:
        raise ValueError("duplicate citation key or DOI")
    record.metadata_verified = True
    record.verification_status = VerificationStatus.VERIFIED
    record.edit_history.append(
        {
            "field": "verification_status",
            "value": "verified",
            "contributor": contributor,
            "edited_at": utc_now(),
        }
    )
    save_index(root, records)
    return record


@mutating("reference enrich crossref")
def enrich_reference(
    root: Path, identifier: str, *, confirm_remote: bool = False
) -> ReferenceRecord:
    """Merge deterministic Crossref DOI metadata and preserve the raw response."""
    records = load_index(root)
    _require_remote_permission(root, confirm_remote)
    record = next((item for item in records if item.id == identifier), None)
    if record is None or not record.doi:
        raise ValueError("reference enrichment requires a DOI")
    provider_name = "crossref"
    try:
        raw = _fetch_crossref(record.doi)
    except CrossrefNotFoundError:
        provider_name = "datacite"
        raw = _fetch_datacite(record.doi)
    snapshot = (
        root
        / "references/provenance"
        / identifier
        / f"{provider_name}-{utc_now().replace(':', '')}.json"
    )
    if provider_name == "crossref":
        _merge_crossref(record, raw)
    else:
        _merge_datacite(record, raw)
    record.source_provenance.append(
        {
            "source": provider_name,
            "captured_at": utc_now(),
            "snapshot": str(snapshot.relative_to(root)),
        }
    )
    if record.verification_status is not VerificationStatus.VERIFIED:
        record.verification_status = VerificationStatus.ENRICHED_UNVERIFIED
    transaction = FileTransaction(root, "reference enrich crossref")
    transaction.stage_text(snapshot, json.dumps(raw, indent=2, sort_keys=True) + "\n")
    transaction.stage_text(root / "references/index.yaml", _index_yaml(records))
    transaction.commit()
    return record


@mutating("reference enrich openalex")
def enrich_openalex(
    root: Path,
    identifier: str,
    api_key: str | None = None,
    *,
    confirm_remote: bool = False,
) -> ReferenceRecord:
    """Optionally enrich a DOI record from OpenAlex without replacing Crossref authority."""
    _require_remote_permission(root, confirm_remote)
    records = load_index(root)
    record = next((item for item in records if item.id == identifier), None)
    if record is None or not record.doi:
        raise ValueError("OpenAlex enrichment requires a DOI")
    raw = _fetch_openalex(record.doi, _resolve_openalex_key(root, api_key))
    snapshot = (
        root / "references/provenance" / identifier / f"openalex-{utc_now().replace(':', '')}.json"
    )
    _merge_openalex(record, raw)
    record.source_provenance.append(
        {
            "source": "openalex",
            "captured_at": utc_now(),
            "snapshot": str(snapshot.relative_to(root)),
        }
    )
    if record.verification_status is not VerificationStatus.VERIFIED:
        record.verification_status = VerificationStatus.ENRICHED_UNVERIFIED
    transaction = FileTransaction(root, "reference enrich openalex")
    transaction.stage_text(snapshot, json.dumps(raw, indent=2, sort_keys=True) + "\n")
    transaction.stage_text(root / "references/index.yaml", _index_yaml(records))
    transaction.commit()
    return record


def _require_remote_permission(root: Path, confirmed: bool) -> None:
    """Require explicit consent before protected-project remote metadata queries."""
    from smairt.models import SmairtConfig

    config = SmairtConfig.load(root / "smairt.yaml")
    protected = config.data.classification.value in {"private", "controlled"}
    if not protected:
        return
    if confirmed:
        return
    mode = config.safety_mode.value
    if mode == "strict":
        raise ValueError("Strict protected projects require --confirm-remote for metadata queries")
    raise ValueError(
        "Protected projects require --confirm-remote for remote metadata queries "
        f"(safety mode: {mode})"
    )


def export_references(root: Path, format_name: str) -> str:
    """Export verified structured records for citation tooling."""
    records = load_index(root)
    unverified = [record.id for record in records if record.verification_status != "verified"]
    if unverified:
        raise ValueError("reference export requires verified records: " + ", ".join(unverified))
    if format_name == "csl-json":
        import json

        items = [
            {
                "id": r.citation_key or r.id,
                "type": r.document_type,
                "title": r.title,
                "author": [{"literal": a} for a in r.authors],
                "issued": {"date-parts": [[r.year]]} if r.year else None,
                "DOI": r.doi,
                "container-title": r.venue,
                "volume": r.volume,
                "issue": r.issue,
                "page": r.pages,
                "URL": r.url,
            }
            for r in records
        ]
        return json.dumps(items, indent=2, ensure_ascii=False) + "\n"
    if format_name != "bibtex":
        raise ValueError("format must be bibtex or csl-json")
    entries = []
    for r in records:
        fields = {
            "title": r.title,
            "author": " and ".join(r.authors),
            "year": str(r.year) if r.year else None,
            "doi": r.doi,
            "journal": r.venue,
            "volume": r.volume,
            "number": r.issue,
            "pages": r.pages,
            "url": r.url,
        }
        body = ",\n".join(f"  {key} = {{{value}}}" for key, value in fields.items() if value)
        entries.append(f"@article{{{r.citation_key or r.id},\n{body}\n}}")
    return "\n\n".join(entries) + ("\n" if entries else "")


def unindexed_pdfs(root: Path) -> list[Path]:
    """List local reference PDFs whose checksums are absent from the index."""
    records = load_index(root)
    known = {record.sha256 for record in records if record.sha256}
    return [
        path
        for path in sorted((root / "references/pdfs").glob("*.pdf"))
        if sha256_file(path) not in known
    ]
