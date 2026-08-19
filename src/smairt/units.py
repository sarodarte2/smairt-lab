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
    stage = "stage"
    question = "question"


def next_stage_number(experiments_dir: Path) -> int:
    """The next unused stage number, so ``smairt unit new`` is the sole numbering authority."""
    numbers = []
    if experiments_dir.is_dir():
        for entry in experiments_dir.iterdir():
            if entry.is_dir():
                head = entry.name.split("_", 1)[0]
                if head.isdigit():
                    numbers.append(int(head))
    return max(numbers, default=0) + 1


def _make_standard_subfolders(unit_dir: Path) -> None:
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
    relative to the project root).
    """
    experiments_dir = project_root / "experiments"
    number = next_stage_number(experiments_dir)
    unit_dir = experiments_dir / f"{number:02d}_{slugify(title, fallback='stage', sep='-')}"
    if unit_dir.exists():
        raise PathExistsError(f"refusing to overwrite existing unit: {unit_dir}")

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
    write_once(unit_dir / "README.md", frontmatter.render(fields) + body)
    if not is_reference:
        _make_standard_subfolders(unit_dir)
    return unit_dir


def create_question(
    project_root: Path,
    title: str,
    *,
    hypothesis: str | None = None,
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
    """
    today = created or date.today()
    slug = slugify(title, fallback="question", sep="-")
    unit_dir = project_root / "experiments" / f"{today.isoformat()}_{slug}"
    if unit_dir.exists():
        raise PathExistsError(f"refusing to overwrite existing unit: {unit_dir}")

    is_reference = bool(ref_paths)
    fields: dict[str, object] = {
        "kind": "question",
        "title": title,
        "status": "open",
        "date": today,
        "hypothesis": hypothesis or "",
        "script": "",
        "log": "" if is_reference else f"logs/{slug}.log",
        "verdict": "",
    }
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
    return STAGE_REQUIRED_FIELDS if kind is UnitKind.stage else QUESTION_REQUIRED_FIELDS


def allowed_statuses(kind: UnitKind) -> Sequence[str]:
    return STAGE_STATUSES if kind is UnitKind.stage else QUESTION_STATUSES
