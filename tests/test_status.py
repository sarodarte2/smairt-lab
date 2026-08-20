"""Tests for ``smairt status`` (src/smairt/status.py): the orientation report.

Covers the spine/live-questions/recently-closed sections, STATUS drift
reporting, and both the human-readable and --json renderings.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from smairt import frontmatter
from smairt.project import Harness, create_project
from smairt.status import build_status_report, render_human, to_json
from smairt.units import create_question, create_stage

GIT_UNAVAILABLE_SUGGESTION = (
    "SMAIRT101 .: not a Git repository: raw-log immutability under logs/ cannot be verified."
)


def _project(tmp_path: Path, **overrides: object) -> Path:
    root = tmp_path / "project"
    defaults: dict[str, object] = dict(
        name="Status Project",
        researcher="Ada Lovelace",
        description="Exercises smairt status.",
        harness=Harness.none,
        hpc=False,
        paper=False,
        created=date.today(),
        scaffold_version="0.0.0-test",
    )
    defaults.update(overrides)
    create_project(root, **defaults)  # type: ignore[arg-type]
    return root


def _set_fields(readme_path: Path, **updates: object) -> None:
    fields, body = frontmatter.read(readme_path)
    fields.update(updates)
    readme_path.write_text(frontmatter.render(fields) + body, encoding="utf-8")


def _freeze_stage(stage_dir: Path) -> None:
    # `out/` is one of the standard subfolders `smairt unit new` already created,
    # so pointing `script:` at it keeps rule SMAIRT002 (evidence pointers) silent.
    _set_fields(stage_dir / "README.md", status="frozen", script="out")


def _close_question(question_dir: Path, *, status: str, verdict: str) -> None:
    readme_path = question_dir / "README.md"
    fields, _body = frontmatter.read(readme_path)
    log_rel = str(fields["log"])
    (question_dir / log_rel).write_text("log output\n", encoding="utf-8")
    _set_fields(readme_path, status=status, script="out", verdict=verdict)


# --- (a) fresh project -----------------------------------------------------------


def test_fresh_project_renders_all_six_sections_with_honest_empty_lines(tmp_path: Path) -> None:
    root = _project(tmp_path)

    report = build_status_report(root)
    text = render_human(report)

    assert text == (
        "Focus:\n"
        "  Exercises smairt status.\n"
        "\n"
        "Next:\n"
        "  Create the first stage or question with `smairt unit new`.\n"
        "\n"
        "Spine:\n"
        "  No stages yet.\n"
        "\n"
        "Live questions:\n"
        "  No open questions.\n"
        "\n"
        "Recently closed:\n"
        "  No closed questions yet.\n"
        "\n"
        "Open questions (STATUS.md):\n"
        "  None recorded.\n"
        "\n"
        "Warnings:\n"
        "  No warnings.\n"
        "\n"
        "Suggestions:\n"
        f"  {GIT_UNAVAILABLE_SUGGESTION}"
    )


def test_fresh_project_has_no_drift_line_and_empty_derived_sections(tmp_path: Path) -> None:
    root = _project(tmp_path)

    report = build_status_report(root)

    assert report.status_updated == date.today().isoformat()
    assert report.drifted_units == ()
    assert report.spine == ()
    assert report.live_questions == ()
    assert report.recently_closed == ()
    assert report.open_questions == ()
    assert report.findings == ()


# --- (b) mid-project: frozen + active stages, open + closed questions ------------


def test_mid_project_spine_and_questions_render_correctly(tmp_path: Path) -> None:
    root = _project(tmp_path)

    stage1 = create_stage(root, "Alignment", created=date(2026, 1, 1))
    _freeze_stage(stage1)
    stage2 = create_stage(root, "Differential expression", created=date(2026, 1, 2))
    _set_fields(stage2 / "README.md", variant_active="deseq2")

    create_question(root, "Does batch correction help?", created=date(2026, 1, 10))
    closed_question = create_question(root, "Replicate 3 outlier?", created=date(2026, 1, 5))
    _close_question(
        closed_question,
        status="refuted",
        verdict="Excluding replicate 3 did not change the DE results.",
    )

    report = build_status_report(root)

    assert [entry.number for entry in report.spine] == ["01", "02"]
    assert report.spine[0].title == "Alignment"
    assert report.spine[0].status == "frozen"
    assert report.spine[0].variant_active is None
    assert report.spine[1].title == "Differential expression"
    assert report.spine[1].variant_active == "deseq2"

    assert [q.title for q in report.live_questions] == ["Does batch correction help?"]
    assert report.live_questions[0].date == "2026-01-10"
    assert report.live_questions[0].status == "open"

    assert [q.title for q in report.recently_closed] == ["Replicate 3 outlier?"]
    assert report.recently_closed[0].status == "refuted"
    assert (
        report.recently_closed[0].verdict == "Excluding replicate 3 did not change the DE results."
    )

    text = render_human(report)
    assert (
        "Spine:\n  01 Alignment — frozen\n  02 Differential expression — active (active: deseq2)"
        in text
    )
    assert "Live questions:\n  2026-01-10  Does batch correction help? — open" in text
    assert (
        "Recently closed:\n  2026-01-05  Replicate 3 outlier? — refuted: "
        "Excluding replicate 3 did not change the DE results."
    ) in text


def test_reference_unit_appears_as_a_live_question_without_crashing(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "data" / "old_analysis").mkdir(parents=True)

    create_question(root, "Old DE run", ref_paths=["data/old_analysis"], created=date(2026, 1, 3))

    report = build_status_report(root)

    assert [q.title for q in report.live_questions] == ["Old DE run"]
    assert report.live_questions[0].status == "open"
    # No exception rendering either format for a unit with no logs/out/figures.
    render_human(report)
    to_json(report)


def test_recently_closed_keeps_only_the_most_recent_three(tmp_path: Path) -> None:
    root = _project(tmp_path)
    for day, title in enumerate(
        ["First close", "Second close", "Third close", "Fourth close"], start=1
    ):
        question = create_question(root, title, created=date(2026, 2, day))
        _close_question(question, status="supported", verdict=f"Verdict for {title}.")

    report = build_status_report(root)

    assert [q.title for q in report.recently_closed] == [
        "Fourth close",
        "Third close",
        "Second close",
    ]


# --- (c) stale STATUS: drift label names exactly the changed units ---------------


def test_stale_status_labels_drift_with_the_changed_unit_names(tmp_path: Path) -> None:
    root = _project(tmp_path)
    stage = create_stage(root, "Alignment", created=date.today())
    question = create_question(root, "Does batch correction help?", created=date.today())
    status_path = root / "STATUS.md"
    status_path.write_text(
        status_path.read_text(encoding="utf-8").replace(str(date.today()), "2020-01-01"),
        encoding="utf-8",
    )

    report = build_status_report(root)

    assert report.status_updated == "2020-01-01"
    expected_units = {stage.name, question.name}
    assert set(report.drifted_units) == expected_units

    text = render_human(report)
    assert "STATUS last written 2020-01-01; changed since:" in text
    for name in expected_units:
        assert name in text


def test_status_with_no_drift_prints_no_drift_line(tmp_path: Path) -> None:
    root = _project(tmp_path)
    create_stage(root, "Alignment", created=date.today())

    report = build_status_report(root)
    text = render_human(report)

    assert report.drifted_units == ()
    assert "changed since" not in text


# --- JSON parity ------------------------------------------------------------------


def test_json_output_mirrors_text_content(tmp_path: Path) -> None:
    root = _project(tmp_path)
    stage = create_stage(root, "Alignment", created=date(2026, 1, 1))
    _freeze_stage(stage)
    create_question(
        root,
        "Does batch correction help?",
        hypothesis="Batch correction removes the batch effect without erasing biology.",
        created=date(2026, 1, 10),
    )

    report = build_status_report(root)
    payload = to_json(report)
    serialized = json.dumps(payload)  # must not raise
    parsed = json.loads(serialized)

    assert parsed["focus"] == report.focus
    assert parsed["next"] == report.next_step
    assert parsed["spine"][0]["title"] == "Alignment"
    assert parsed["spine"][0]["status"] == "frozen"
    assert parsed["live_questions"][0]["title"] == "Does batch correction help?"
    assert parsed["recently_closed"] == []
    assert "summary" in parsed
    assert parsed["summary"]["errors"] == 0


# --- side effect: results/INDEX.md regenerated ------------------------------------


def test_building_report_regenerates_results_index(tmp_path: Path) -> None:
    root = _project(tmp_path)
    create_stage(root, "Alignment", created=date.today())
    index_path = root / "results" / "INDEX.md"
    index_path.write_text("stale content\n", encoding="utf-8")

    build_status_report(root)

    updated = index_path.read_text(encoding="utf-8")
    assert updated != "stale content\n"
    assert "01_alignment" in updated
