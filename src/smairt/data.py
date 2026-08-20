"""``smairt data`` — records where each dataset's bytes physically live.

Research data is usually too big for Git (or lives on an HPC scratch disk a
collaborator can't reach from a laptop), so ``data/<slug>/`` in the generated
scaffold is git-ignored except for its README (see ``_GITIGNORE`` and
``_DATA_README`` in :mod:`smairt.project`). A collaborator who clones the
project gets every README but none of the bytes those READMEs describe --
this module is what lets the README also say *where the bytes actually are*.

The design is **per-dataset frontmatter**, not a central registry file: truth
lives next to the dataset it describes, in the same YAML block every other
README in this codebase uses (see :mod:`smairt.frontmatter`). A single
``data/locations.yaml`` would be one file every collaborating researcher's
concurrent edits collide on; a per-dataset README is not, and it is where a
researcher is already looking when they wonder "where is this data."

A dataset README's frontmatter has exactly two fields: ``dataset:`` (the
slug, matching the folder name) and ``locations:`` (a list of
:class:`Location`). Everything below the frontmatter is free-form provenance
prose (where the data came from, when, what was already done to it) --
structural only, same as every other reader in this codebase: this module
never inspects or judges that prose.

Public functions, one per responsibility:

* :func:`create_dataset` -- ``smairt data new``. Creates the folder + README,
  always recording a ``local`` location pointing at the dataset folder
  itself (that is where it lives, by definition, once created) plus any
  caller-supplied locations.
* :func:`add_location` -- ``smairt data locate``. Appends one more location
  to an existing dataset's README, idempotently.
* :func:`list_locations` -- ``smairt data list``. Scans every dataset under
  ``data/`` and reports its recorded locations, tolerant of a hand-written
  README with no frontmatter or no ``locations:`` at all (researchers write
  these by hand; a typo shouldn't crash the command).

Judgment calls a reviewer should know about
--------------------------------------------
* :func:`add_location` compares and appends **raw** location mappings, not
  parsed :class:`Location` objects, and never re-serializes the locations
  already on file. If a researcher hand-wrote an entry this module's own
  parser can't fully make sense of, appending a new location must not
  silently discard it -- only :func:`list_locations` (read-only, display
  only) does the tolerant parse-and-skip.
* ``kind`` validation (one of ``local``/``hpc``/``url``) and the
  ``host``-required-for-``hpc`` rule live in :meth:`Location.__post_init__`,
  so every code path that can construct a :class:`Location` -- CLI flag
  parsing, :func:`create_dataset`'s automatic local entry, a caller passing
  ``locations=`` directly -- is validated the same way, in one place.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from smairt import frontmatter
from smairt.fsutil import write_once
from smairt.text import slugify

LOCATION_KINDS = ("local", "hpc", "url")

_DATASET_README_BODY = (
    "\n## Provenance\n\n"
    "Where this data came from, when, and any transform already applied before it "
    "landed here. Free-form prose -- update it as the dataset changes.\n"
)


@dataclass(frozen=True)
class Location:
    """One place a dataset's bytes can be found.

    ``kind`` is ``local`` (a path inside this project's ``data/``), ``hpc``
    (a path on a named remote host), or ``url`` (a download source). ``path``
    is required for every kind; ``host`` is required for ``hpc`` and
    meaningless otherwise; ``note`` is always optional free text (e.g. "raw
    download" or "mirrored nightly").

    Validated on construction (see the module docstring) so an invalid
    ``Location`` can never exist long enough to be written to disk.
    """

    kind: str
    path: str
    host: str | None = None
    note: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in LOCATION_KINDS:
            raise ValueError(f"location kind {self.kind!r} is not one of {LOCATION_KINDS}")
        if not self.path.strip():
            raise ValueError("location 'path' is required")
        if self.kind == "hpc" and not (self.host and self.host.strip()):
            raise ValueError("location kind 'hpc' requires 'host'")


@dataclass(frozen=True)
class DatasetEntry:
    """One dataset under ``data/`` and everything :func:`list_locations` knows about it."""

    dataset: str
    path: str
    locations: tuple[Location, ...]


@dataclass(frozen=True)
class DataReport:
    """The full result of :func:`list_locations` -- every dataset found under ``data/``."""

    entries: tuple[DatasetEntry, ...]


def _location_to_fields(location: Location) -> dict[str, str]:
    """Render one :class:`Location` as the ordered mapping the frontmatter schema uses.

    Field order (``kind``, then ``host`` if present, then ``path``, then
    ``note`` if present) matches the data contract's example verbatim --
    ``host`` reads naturally right after ``kind`` for an ``hpc`` entry,
    before the path it qualifies.
    """
    fields: dict[str, str] = {"kind": location.kind}
    if location.host:
        fields["host"] = location.host
    fields["path"] = location.path
    if location.note:
        fields["note"] = location.note
    return fields


def _location_from_mapping(raw: Any) -> Location | None:
    """Best-effort parse of one raw ``locations:`` list entry into a :class:`Location`.

    Returns ``None`` for anything that isn't a mapping, or whose fields fail
    :class:`Location`'s own validation -- used only by the read-only,
    display-only :func:`list_locations`, so a hand-written mistake becomes
    "this dataset has one fewer location than it should" rather than a crash.
    """
    if not isinstance(raw, Mapping):
        return None
    try:
        return Location(
            kind=str(raw.get("kind", "")),
            path=str(raw.get("path", "")),
            host=str(raw["host"]) if raw.get("host") else None,
            note=str(raw["note"]) if raw.get("note") else None,
        )
    except ValueError:
        return None


def create_dataset(
    project_root: Path,
    name: str,
    *,
    locations: Sequence[Location] = (),
) -> Path:
    """Create ``data/<slug>/README.md``, recording where this dataset's bytes live.

    Always records a ``local`` location pointing at the dataset folder
    itself first -- that is where the data lives by definition once this
    folder exists -- followed by any caller-supplied ``locations`` (an HPC
    mirror, a download URL, ...). Written via :func:`smairt.fsutil.write_once`,
    so creating a dataset that already exists raises
    :class:`~smairt.fsutil.PathExistsError` instead of silently merging into
    it -- the same "written once" promise every other skeleton in this
    codebase makes; use :func:`add_location` to add a location afterward.
    """
    slug = slugify(name, fallback="dataset")
    dataset_dir = project_root / "data" / slug

    local = Location(kind="local", path=f"data/{slug}/")
    all_locations = (local, *locations)

    fields: dict[str, object] = {
        "dataset": slug,
        "locations": [_location_to_fields(loc) for loc in all_locations],
    }
    write_once(dataset_dir / "README.md", frontmatter.render(fields) + _DATASET_README_BODY)
    return dataset_dir


def add_location(project_root: Path, dataset: str, location: Location) -> Path:
    """Add ``location`` to an existing dataset's README, unless it is already recorded.

    "Already recorded" means an identical raw mapping already sits in
    ``locations:`` -- appending is a no-op in that case, so calling this
    twice with the same location is safe (idempotent). Raises ``ValueError``
    if ``dataset`` has no ``data/<slug>/README.md`` yet (create it first with
    :func:`create_dataset`). See the module docstring for why this works on
    raw mappings rather than round-tripping through parsed :class:`Location`
    objects.
    """
    slug = slugify(dataset, fallback="dataset")
    readme_path = project_root / "data" / slug / "README.md"
    if not readme_path.is_file():
        raise ValueError(
            f"no dataset found at data/{slug}/README.md (create it first with `smairt data new`)"
        )

    fields, body = frontmatter.read(readme_path)
    raw_locations = fields.get("locations")
    existing: list[Any] = list(raw_locations) if isinstance(raw_locations, list) else []

    new_entry = _location_to_fields(location)
    if new_entry not in existing:
        existing.append(new_entry)

    fields["locations"] = existing
    readme_path.write_text(frontmatter.render(fields) + body, encoding="utf-8")
    return readme_path.parent


def list_locations(project_root: Path) -> DataReport:
    """Scan every ``data/<slug>/README.md`` and report its recorded locations.

    Skips ``data/README.md`` itself (the folder's own guidance file, not a
    dataset -- it naturally never matches, since only subfolders are
    scanned). Tolerant of a dataset README with no frontmatter block at all,
    or frontmatter with no ``locations:`` list: either becomes a
    :class:`DatasetEntry` with zero locations rather than an error, since
    researchers write these files by hand.
    """
    data_dir = project_root / "data"
    if not data_dir.is_dir():
        return DataReport(entries=())

    entries: list[DatasetEntry] = []
    for entry in sorted(data_dir.iterdir(), key=lambda item: item.name):
        if not entry.is_dir():
            continue
        readme = entry / "README.md"
        dataset_name = entry.name
        locations: tuple[Location, ...] = ()
        if readme.is_file():
            try:
                fields, _body = frontmatter.read(readme)
            except frontmatter.FrontmatterError:
                fields = {}
            dataset_name = str(fields.get("dataset", entry.name))
            raw_locations = fields.get("locations")
            if isinstance(raw_locations, list):
                locations = tuple(
                    loc for loc in (_location_from_mapping(item) for item in raw_locations) if loc
                )
        entries.append(
            DatasetEntry(dataset=dataset_name, path=f"data/{entry.name}", locations=locations)
        )
    return DataReport(entries=tuple(entries))


# --- output rendering ---------------------------------------------------------


def render_human(report: DataReport) -> str:
    """Render every dataset and its locations as plain aligned text."""
    if not report.entries:
        return "No datasets found under data/."

    lines: list[str] = []
    for entry in report.entries:
        lines.append(f"{entry.dataset} ({entry.path})")
        if not entry.locations:
            lines.append("  (no locations recorded)")
            continue
        for location in entry.locations:
            target = f"{location.host}:{location.path}" if location.host else location.path
            note = f"  # {location.note}" if location.note else ""
            lines.append(f"  {location.kind:<5} {target}{note}")
    return "\n".join(lines)


def to_json(report: DataReport) -> dict[str, Any]:
    """Render ``report`` as the ``--json`` payload: one entry per dataset."""
    return {
        "datasets": [
            {
                "dataset": entry.dataset,
                "path": entry.path,
                "locations": [asdict(location) for location in entry.locations],
            }
            for entry in report.entries
        ]
    }
