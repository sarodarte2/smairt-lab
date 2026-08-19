"""``smairt status`` — orientation (WP3).

The four returning-researcher questions (ticket 05: what was I doing, what next,
what routes exist, how did I get here), answered under one screen from derived
state + ``STATUS.md`` — the project's one hand-maintained ledger (Part I,
foundation 3). This module reads; it does not reimplement `smairt check`'s
drift detection or finding machinery, it reuses :func:`smairt.check.run_checks`
and :func:`smairt.check.read_status` directly.

Public entry point: :func:`build_status_report`, returning a :class:`StatusReport`.
Render with :func:`render_human` or :func:`to_json`.

Side effect: building a report regenerates ``results/INDEX.md`` (via
:func:`smairt.index.write_index`) — the one write this command is allowed
(Part I, foundation 3: derived-first state; everything else here is read-only).

Judgment calls a reviewer should know about
--------------------------------------------
* "Recently closed" and "Live questions" both sort by the question's
  frontmatter ``date:`` field (its ISO form sorts correctly as a string) —
  there is no separate "closed on" field in the schema, so a question's
  creation date is the only date available to order by.
* The staleness label (drifted units) names units by folder name only
  (``experiments/`` stripped), matching how the spine and question sections
  already refer to units — not the full ``Finding.path``.
* A unit whose README fails to parse is silently skipped here (not counted in
  the spine or question lists); `smairt check`'s SMAIRT001 finding is what
  reports that problem, and it still appears in the Warnings section below.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from smairt import check as check_module
from smairt import frontmatter
from smairt import index as index_module
from smairt import units as units_module
from smairt.check import Finding, Suggestion

RECENTLY_CLOSED_LIMIT = 3

_CLOSED_QUESTION_STATUSES = frozenset(units_module.QUESTION_STATUSES) - {"open"}


@dataclass(frozen=True)
class SpineEntry:
    """One stage on the spine."""

    path: str
    number: str
    title: str
    status: str
    variant_active: str | None


@dataclass(frozen=True)
class QuestionEntry:
    """One question unit, open or closed."""

    path: str
    date: str
    title: str
    status: str
    verdict: str


@dataclass(frozen=True)
class StatusReport:
    """Everything ``smairt status`` prints, derived from project files + a CheckReport."""

    focus: str
    next_step: str
    status_updated: str | None
    drifted_units: tuple[str, ...]
    spine: tuple[SpineEntry, ...]
    live_questions: tuple[QuestionEntry, ...]
    recently_closed: tuple[QuestionEntry, ...]
    open_questions: tuple[str, ...]
    findings: tuple[Finding, ...]
    suggestions: tuple[Suggestion, ...]


def build_status_report(project_root: Path) -> StatusReport:
    """Build a :class:`StatusReport` for the project at ``project_root``.

    Reuses `smairt check`'s :func:`~smairt.check.run_checks` for findings/suggestions
    (including STATUS drift, rule SMAIRT005) and :func:`~smairt.check.read_status` for
    STATUS.md's Focus/Next/Open-questions sections — the single STATUS.md reader.
    Regenerates ``results/INDEX.md`` as a side effect.
    """
    status_doc = check_module.read_status(project_root)
    check_report = check_module.run_checks(project_root)

    drifted_units = tuple(
        _unit_name(finding.path)
        for finding in check_report.findings
        if finding.id == check_module.RULE_STATUS_DRIFT
    )

    spine: list[SpineEntry] = []
    live_questions: list[QuestionEntry] = []
    closed_questions: list[QuestionEntry] = []

    # Sort every unit into exactly one bucket by its frontmatter kind/status:
    # stages all go on the spine; questions split into "still open" vs.
    # "closed" (dropping any status this schema doesn't recognize, which
    # `smairt check`'s SMAIRT001 rule would already be flagging separately).
    for entry, fields in _iter_units(project_root):
        kind = fields.get("kind")
        rel = f"experiments/{entry.name}"
        if kind == "stage":
            number = entry.name.split("_", 1)[0]
            variant_active = fields.get("variant_active")
            spine.append(
                SpineEntry(
                    path=rel,
                    number=number,
                    title=str(fields.get("title", entry.name)),
                    status=str(fields.get("status", "")),
                    variant_active=str(variant_active) if variant_active else None,
                )
            )
        elif kind == "question":
            question = QuestionEntry(
                path=rel,
                date=_format_date(fields.get("date")),
                title=str(fields.get("title", entry.name)),
                status=str(fields.get("status", "")),
                verdict=str(fields.get("verdict") or ""),
            )
            if question.status == "open":
                live_questions.append(question)
            elif question.status in _CLOSED_QUESTION_STATUSES:
                closed_questions.append(question)

    live_questions.sort(key=lambda question: question.date, reverse=True)
    closed_questions.sort(key=lambda question: question.date, reverse=True)

    index_module.write_index(project_root)

    return StatusReport(
        focus=status_doc.focus if status_doc else "",
        next_step=status_doc.next_step if status_doc else "",
        status_updated=(
            status_doc.updated.isoformat() if status_doc and status_doc.updated else None
        ),
        drifted_units=drifted_units,
        spine=tuple(spine),
        live_questions=tuple(live_questions),
        recently_closed=tuple(closed_questions[:RECENTLY_CLOSED_LIMIT]),
        open_questions=status_doc.open_questions if status_doc else (),
        findings=check_report.findings,
        suggestions=check_report.suggestions,
    )


# --- loading -------------------------------------------------------------------


def _iter_units(project_root: Path) -> Iterator[tuple[Path, dict[str, Any]]]:
    """Yield ``(unit_dir, frontmatter_fields)`` for every parseable unit under experiments/.

    A unit whose README fails to parse is skipped (`smairt check` already reports
    that via SMAIRT001); folder order already reads top-down (numbered stages
    sort above dated questions), matching :func:`smairt.index.scan_units`.
    """
    experiments_dir = project_root / "experiments"
    if not experiments_dir.is_dir():
        return
    for entry in sorted(experiments_dir.iterdir(), key=lambda item: item.name):
        readme = entry / "README.md"
        if not entry.is_dir() or not readme.is_file():
            continue
        try:
            fields, _body = frontmatter.read(readme)
        except frontmatter.FrontmatterError:
            continue
        yield entry, fields


def _format_date(value: Any) -> str:
    """Turn a frontmatter ``date:`` value into an ISO string for display/sorting.

    PyYAML parses an unquoted ``2026-08-12`` into a real ``date`` object, but
    a malformed or quoted value could come through as a plain string (or be
    missing). This normalizes all three cases to one consistent output.
    """
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value) if value else ""


def _unit_name(rel_path: str) -> str:
    """Strip a leading ``experiments/`` so units are named the way the spine names them."""
    prefix = "experiments/"
    return rel_path[len(prefix) :] if rel_path.startswith(prefix) else rel_path


# --- rendering -------------------------------------------------------------------


def render_human(report: StatusReport) -> str:
    """Render the six sections (Part III, WP3), plainly and under one screen."""
    lines: list[str] = []

    lines.append("Focus:")
    lines.append(f"  {report.focus or '(not set)'}")
    lines.append("")
    lines.append("Next:")
    lines.append(f"  {report.next_step or '(not set)'}")
    if report.status_updated is not None and report.drifted_units:
        lines.append("")
        lines.append(
            f"STATUS last written {report.status_updated}; changed since: "
            f"{', '.join(report.drifted_units)}"
        )
    lines.append("")

    lines.append("Spine:")
    if report.spine:
        for stage in report.spine:
            variant = f" (active: {stage.variant_active})" if stage.variant_active else ""
            lines.append(f"  {stage.number} {stage.title} — {stage.status}{variant}")
    else:
        lines.append("  No stages yet.")
    lines.append("")

    lines.append("Live questions:")
    if report.live_questions:
        for question in report.live_questions:
            lines.append(f"  {question.date}  {question.title} — {question.status}")
    else:
        lines.append("  No open questions.")
    lines.append("")

    lines.append("Recently closed:")
    if report.recently_closed:
        for question in report.recently_closed:
            lines.append(
                f"  {question.date}  {question.title} — {question.status}: {question.verdict}"
            )
    else:
        lines.append("  No closed questions yet.")
    lines.append("")

    lines.append("Open questions (STATUS.md):")
    if report.open_questions:
        lines.extend(f"  - {item}" for item in report.open_questions)
    else:
        lines.append("  None recorded.")
    lines.append("")

    lines.append("Warnings:")
    if report.findings:
        lines.extend(
            f"  {finding.id} {finding.path}: {finding.message}" for finding in report.findings
        )
    else:
        lines.append("  No warnings.")

    if report.suggestions:
        lines.append("")
        lines.append("Suggestions:")
        lines.extend(
            f"  {suggestion.id} {suggestion.path}: {suggestion.message}"
            for suggestion in report.suggestions
        )

    return "\n".join(lines)


def to_json(report: StatusReport) -> dict[str, Any]:
    """Render ``report`` as the ``--json`` payload: same content as :func:`render_human`."""
    errors = sum(1 for finding in report.findings if finding.severity == check_module.ERROR)
    warnings = sum(1 for finding in report.findings if finding.severity == check_module.WARNING)
    return {
        "focus": report.focus,
        "next": report.next_step,
        "status_updated": report.status_updated,
        "drifted_units": list(report.drifted_units),
        "spine": [asdict(stage) for stage in report.spine],
        "live_questions": [asdict(question) for question in report.live_questions],
        "recently_closed": [asdict(question) for question in report.recently_closed],
        "open_questions": list(report.open_questions),
        "findings": [asdict(finding) for finding in report.findings],
        "suggestions": [asdict(suggestion) for suggestion in report.suggestions],
        "summary": {
            "errors": errors,
            "warnings": warnings,
            "suggestions": len(report.suggestions),
        },
    }
