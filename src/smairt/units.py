"""``smairt unit new`` — creates one "unit" of research work: a stage or a question.

A unit is a folder under ``experiments/`` with a README (whose top holds a
YAML frontmatter block — see :mod:`smairt.frontmatter`) plus, usually,
``logs/``, ``out/``, and ``figures/`` subfolders. This module is the ONLY
code that creates those folders; a researcher (or an assistant harness) is
never supposed to ``mkdir`` one by hand, because this module is also what
assigns the number (for a stage) or reads today's date (for a question) —
being the sole creator is what keeps that numbering consistent.

Two kinds of unit, named by :class:`UnitKind`:

* **stage** — one step of the project's "spine" (the planned sequence of
  work). Folder name: ``NN_slug`` (e.g. ``01_align_reads``). Numbers assign
  automatically and only ever go up.
* **question** — one exploratory probe, dated rather than numbered. Folder
  name: ``YYYY-MM-DD_slug`` (e.g. ``2026-08-12_why-is-signal-low``).

A third case — a *reference* unit (thin, README-only, pointing at code that
already exists outside ``experiments/``) — is not a separate kind; it's what
you get when ``ref_paths`` is passed to either creator function below (used
by ``smairt adopt`` for pre-existing projects).

A question can also carry ``prompted_by:`` — an OPTIONAL field, set only when
``--from <origin-unit-folder>`` is passed to :func:`create_question`, naming
the unit whose result raised this one as a new, separately testable question
(spec ticket 01, "sidequest lineage"). It is never required and is not part
of :data:`QUESTION_REQUIRED_FIELDS`; :mod:`smairt.check` flags it only when
it is present and dangling.

This module also defines the schemas (:data:`STAGE_REQUIRED_FIELDS`,
:data:`QUESTION_REQUIRED_FIELDS`, and the allowed ``status:`` values) that
:mod:`smairt.check` validates every unit's frontmatter against — so field
names and status values here and in ``check.py`` must always agree.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from pathlib import Path
from typing import Sequence

from smairt import frontmatter
from smairt.fsutil import PathExistsError, write_once
from smairt.text import slugify

# Schemas below match spec Part II exactly: field names and allowed status values
# are the machine-readable contract `smairt check` (WP2) will validate against.

STAGE_STATUSES = ("active", "frozen", "dead-end")
QUESTION_STATUSES = ("open", "supported", "refuted", "inconclusive", "dead-end")

STAGE_REQUIRED_FIELDS = ("kind", "title", "status", "created", "script", "log")
QUESTION_REQUIRED_FIELDS = (
    "kind",
    "title",
    "status",
    "date",
    "hypothesis",
    "script",
    "log",
    "verdict",
)
RECEIPT_FIELDS = ("tool", "tool_version", "command", "repo")

_UNIT_SUBFOLDERS = ("logs", "out", "figures")

_QUESTION_BODY_SECTIONS = (
    "## Why ask this",
    "## What we expected",
    "## Analysis plan",
    "## What happened",
    "## What it means",
    "## Next",
)

# Case 3 (spec Part II, "The three unit cases"): a reference unit is thin —
# README only, no logs/out/figures — pointing at code/output that already
# exists outside experiments/ (how a pre-existing project gets adopted). Its
# README body skips the run-oriented sections entirely.
_REFERENCE_BODY = (
    "\n## What this references and why it matters\n\n"
    "One paragraph: what lives at the referenced path(s), and why it matters "
    "to this project.\n"
)


class UnitKind(str, Enum):
    """The two kinds of unit a researcher can create directly."""

    stage = "stage"
    question = "question"


def next_stage_number(experiments_dir: Path) -> int:
    """The next unused stage number, so ``smairt unit new`` is the sole numbering authority.

    Looks at every folder name directly under ``experiments/``, takes the part
    before the first underscore, and treats it as a number if it's all
    digits (e.g. ``"02_align"`` -> ``2``). Ignores anything that doesn't look
    like a stage (question folders start with a date, not a bare number).
    Returns 1 for a project with no stages yet.
    """
    numbers = []
    if experiments_dir.is_dir():
        for entry in experiments_dir.iterdir():
            if entry.is_dir():
                head = entry.name.split("_", 1)[0]
                if head.isdigit():
                    numbers.append(int(head))
    return max(numbers, default=0) + 1


def _validate_ref_paths(project_root: Path, ref_paths: Sequence[str]) -> None:
    """Validate every ``--ref`` target exists, at creation, the same way ``--from`` does.

    ``--ref`` points at pre-existing code by definition — a reference unit
    (case 3) is exactly "code that already exists elsewhere in the tree", so
    unlike ``--from`` (whose origin unit could conceivably not exist yet in
    some odd ordering) there is no legitimate forward reference to allow.
    Before this validation existed, ``smairt unit new --help`` promised
    ``--from`` was "Validated to exist at creation" but said nothing for
    ``--ref``, and a nonexistent/absolute/``..``-escaping ``--ref`` was
    silently accepted, only (sometimes) caught later by `smairt check`'s
    rule SMAIRT002 — or not caught at all for an absolute path that happens
    to exist somewhere else on the machine (DG-5). This closes that gap the
    same way ``create_question``'s ``prompted_by`` validation closes the
    equivalent gap for ``--from``: a plain ``ValueError`` naming the exact
    problem, raised before any file is written.

    Rejects, in order: an absolute path (never legitimate — every pointer
    field in this project is documented as relative, see
    :mod:`smairt.check`'s :func:`~smairt.check._pointer_resolves`); a path
    that resolves outside ``project_root`` via ``..`` segments; and a path
    that, once confirmed to stay inside the project, doesn't actually exist.
    """
    resolved_root = project_root.resolve()
    for target in ref_paths:
        candidate = Path(target)
        if candidate.is_absolute():
            raise ValueError(
                f"--ref must be relative to the project root, not absolute: {target!r} "
                "(pass the path the way you'd see it from the project's top level)."
            )
        resolved = (project_root / candidate).resolve()
        if not resolved.is_relative_to(resolved_root):
            raise ValueError(
                f"--ref escapes the project root: {target!r} resolves to {resolved}, "
                f"which is outside {resolved_root} (remove the leading '../' segments)."
            )
        if not resolved.exists():
            raise ValueError(
                f"--ref target does not exist: {target!r} "
                "(check the path, or create it before referencing it here)."
            )


def _make_standard_subfolders(unit_dir: Path) -> None:
    """Create ``logs/``, ``out/``, ``figures/`` inside a unit, each holding a ``.gitkeep``.

    Git does not track empty folders, so an empty ``.gitkeep`` placeholder
    file is what makes these subfolders actually show up once committed —
    even before any real log or figure has been written into them.
    """
    for name in _UNIT_SUBFOLDERS:
        folder = unit_dir / name
        folder.mkdir(parents=True, exist_ok=True)
        keep = folder / ".gitkeep"
        if not keep.exists():
            keep.write_text("", encoding="utf-8")


def _receipt_fields(
    *,
    tool: str | None,
    tool_version: str | None,
    command: str | None,
    repo: str | None,
) -> dict[str, str]:
    """Build the frontmatter fields for a "receipt" unit (one that ran an outside tool).

    A receipt records enough to reproduce or audit an external tool's run
    without copying the tool itself into the project: which tool, which
    version, the exact command, and (optionally) where its source lives.
    Missing text fields become empty strings rather than being left out, so
    the frontmatter schema stays consistent across every receipt unit.
    """
    if not tool:
        raise ValueError("--receipt requires --tool")
    return {
        "tool": tool,
        "tool_version": tool_version or "",
        "command": command or "",
        "repo": repo or "",
    }


def create_stage(
    project_root: Path,
    title: str,
    *,
    receipt: bool = False,
    tool: str | None = None,
    tool_version: str | None = None,
    command: str | None = None,
    repo: str | None = None,
    created: date | None = None,
    ref_paths: Sequence[str] | None = None,
) -> Path:
    """Create ``experiments/NN_slug/`` — one step of the spine.

    ``ref_paths`` (case 3, spec Part II): a non-empty sequence makes this a
    thin reference unit — README only, no logs/out/figures/ — whose
    frontmatter carries ``paths:`` (the referenced pre-existing paths,
    relative to the project root). Each path is validated at creation (see
    :func:`_validate_ref_paths`) exactly as ``--from`` is: it must exist,
    must be relative, and must not escape the project root via ``..``.
    """
    if ref_paths:
        _validate_ref_paths(project_root, ref_paths)

    experiments_dir = project_root / "experiments"
    number = next_stage_number(experiments_dir)
    unit_dir = experiments_dir / f"{number:02d}_{slugify(title, fallback='stage', sep='-')}"
    if unit_dir.exists():
        raise PathExistsError(f"refusing to overwrite existing unit: {unit_dir}")

    # Passing --ref makes this a "reference" unit (case 3): thin, README-only,
    # pointing at code/output that already lives outside experiments/. Every
    # branch below checks is_reference to skip the run-oriented parts (a
    # logs/ pointer, logs/out/figures subfolders, the run-report body).
    is_reference = bool(ref_paths)
    fields: dict[str, object] = {
        "kind": "stage",
        "title": title,
        "status": "active",
        "created": created or date.today(),
        "script": "",
        "log": "" if is_reference else "logs/",
    }
    if is_reference:
        fields["paths"] = list(ref_paths)  # type: ignore[arg-type]
    if receipt:
        fields.update(
            _receipt_fields(tool=tool, tool_version=tool_version, command=command, repo=repo)
        )

    if is_reference:
        body = _REFERENCE_BODY
    else:
        body = (
            "\n## Purpose\n\n"
            "One line: what this stage settles.\n\n"
            "## Approach\n\n"
            "How it is done today (script or method). Update this if the approach changes.\n\n"
            "## Result\n\n"
            "Filled in once this stage has output. If it holds variants, name the active one "
            "and why the others lost.\n"
        )
    # write_once (not a plain write) means this errors instead of clobbering if
    # the folder somehow already has a README — see smairt.fsutil.
    write_once(unit_dir / "README.md", frontmatter.render(fields) + body)
    if not is_reference:
        _make_standard_subfolders(unit_dir)
    return unit_dir


def create_question(
    project_root: Path,
    title: str,
    *,
    hypothesis: str | None = None,
    prompted_by: str | None = None,
    receipt: bool = False,
    tool: str | None = None,
    tool_version: str | None = None,
    command: str | None = None,
    repo: str | None = None,
    created: date | None = None,
    ref_paths: Sequence[str] | None = None,
) -> Path:
    """Create ``experiments/YYYY-MM-DD_slug/`` — one exploratory probe.

    ``ref_paths`` (case 3, spec Part II): a non-empty sequence makes this a
    thin reference unit — README only, no logs/out/figures/ — whose
    frontmatter carries ``paths:`` (the referenced pre-existing paths,
    relative to the project root).

    ``prompted_by`` (``--from`` on the CLI) names the folder of the unit
    whose result raised this question — the sidequest-lineage link (spec
    ticket 01). It is validated here, at creation, the same way ``--tool``
    is validated by :func:`_receipt_fields`: a ``prompted_by`` naming a
    folder with no README.md under ``experiments/`` raises ``ValueError``
    immediately rather than being written and only caught later by
    ``smairt check``. The field is never required — pass nothing and no
    ``prompted_by:`` line is written at all.
    """
    if ref_paths:
        _validate_ref_paths(project_root, ref_paths)

    today = created or date.today()
    slug = slugify(title, fallback="question", sep="-")
    unit_dir = project_root / "experiments" / f"{today.isoformat()}_{slug}"
    if unit_dir.exists():
        raise PathExistsError(f"refusing to overwrite existing unit: {unit_dir}")

    if prompted_by is not None:
        origin_readme = project_root / "experiments" / prompted_by / "README.md"
        if not origin_readme.is_file():
            raise ValueError(
                f"--from target does not exist: no unit at experiments/{prompted_by} "
                "(check the folder name, or create that unit first)"
            )

    is_reference = bool(ref_paths)
    fields: dict[str, object] = {
        "kind": "question",
        "title": title,
        "status": "open",
        "date": today,
        "hypothesis": hypothesis or "",
    }
    if prompted_by is not None:
        fields["prompted_by"] = prompted_by
    fields["script"] = ""
    fields["log"] = "" if is_reference else f"logs/{slug}.log"
    fields["verdict"] = ""
    if is_reference:
        fields["paths"] = list(ref_paths)  # type: ignore[arg-type]
    if receipt:
        fields.update(
            _receipt_fields(tool=tool, tool_version=tool_version, command=command, repo=repo)
        )

    body = _REFERENCE_BODY if is_reference else "\n" + "\n\n".join(_QUESTION_BODY_SECTIONS) + "\n"
    write_once(unit_dir / "README.md", frontmatter.render(fields) + body)
    if not is_reference:
        _make_standard_subfolders(unit_dir)
    return unit_dir


def required_fields(kind: UnitKind) -> Sequence[str]:
    """The frontmatter field names every unit of this ``kind`` must have. Used by `smairt check`."""
    return STAGE_REQUIRED_FIELDS if kind is UnitKind.stage else QUESTION_REQUIRED_FIELDS


def allowed_statuses(kind: UnitKind) -> Sequence[str]:
    """The legal ``status:`` values for this ``kind``. Used by `smairt check`."""
    return STAGE_STATUSES if kind is UnitKind.stage else QUESTION_STATUSES
