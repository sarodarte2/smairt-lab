"""Tests for ``smairt check`` (src/smairt/check.py): the thirteen state-contract rules.

Each rule (SMAIRT001-013, plus the SMAIRT1xx advisory suggestions) gets its
own section below, marked with a ``# ---`` header matching the rule's name in
check.py. ``_project`` builds a throwaway project per test; ``_set_fields``
edits one unit's frontmatter to provoke (or fix) a specific finding.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import date
from pathlib import Path

import yaml

from smairt import frontmatter
from smairt.check import (
    ERROR,
    RULE_ANALYSIS_PLAN,
    RULE_CLOSED_QUESTION,
    RULE_EVIDENCE_POINTERS,
    RULE_FRONTMATTER,
    RULE_HYPOTHESIS_NONEMPTY,
    RULE_LOG_IMMUTABILITY,
    RULE_MISSING_README,
    RULE_PROJECT_CONFIG,
    RULE_PROMPTED_BY,
    RULE_PROMPTED_BY_CYCLE,
    RULE_RECEIPT_COMPLETENESS,
    RULE_STATUS_DRIFT,
    RULE_STRUCTURE_DRIFT,
    SUGGEST_DATASET_LOCATIONS,
    SUGGEST_GIT_UNAVAILABLE,
    SUGGEST_GROUPING,
    SUGGEST_HPC,
    SUGGEST_PAPER_OVERLAY,
    WARNING,
    render_human,
    run_checks,
    to_json,
)
from smairt.data import create_dataset
from smairt.project import Harness, create_project
from smairt.units import create_question, create_stage

GOLDEN_FIXTURE = Path(__file__).parent / "fixtures" / "golden"


def _project(tmp_path: Path, **overrides: object) -> Path:
    root = tmp_path / "project"
    defaults: dict[str, object] = dict(
        name="Check Project",
        researcher="Ada Lovelace",
        description="Exercises smairt check.",
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


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True)


# --- clean fixtures ------------------------------------------------------------


def test_golden_fixture_passes_clean() -> None:
    report = run_checks(GOLDEN_FIXTURE)

    assert report.findings == ()
    assert report.exit_code == 0


def test_fresh_project_passes_clean(tmp_path: Path) -> None:
    root = _project(tmp_path)

    report = run_checks(root)

    assert report.findings == ()
    assert report.exit_code == 0


def test_fresh_stage_and_question_pass_clean(tmp_path: Path) -> None:
    root = _project(tmp_path)
    create_stage(root, "Alignment", created=date.today())
    create_question(
        root,
        "Does batch correction help?",
        hypothesis="Batch correction removes the batch effect without erasing biology.",
        created=date.today(),
    )

    report = run_checks(root)

    assert report.findings == ()


# --- rule 1: frontmatter schema -------------------------------------------------


def test_rule1_malformed_frontmatter_is_flagged(tmp_path: Path) -> None:
    root = _project(tmp_path)
    stage = create_stage(root, "Alignment", created=date.today())
    (stage / "README.md").write_text("no frontmatter block here\n", encoding="utf-8")

    report = run_checks(root)

    assert {f.id for f in report.findings} == {RULE_FRONTMATTER}


def test_rule1_yaml_broken_inside_a_well_formed_block_is_flagged_not_a_crash(
    tmp_path: Path,
) -> None:
    """Regression for the walk's worst finding: an unclosed `tags: [` list inside
    an otherwise well-formed `---` block used to crash `check` (and `status`/
    `index`) with a raw `yaml.parser.ParserError`. It must become an ordinary
    SMAIRT001 finding instead, the same as any other malformed frontmatter."""
    root = _project(tmp_path)
    stage = create_stage(root, "Alignment", created=date.today())
    (stage / "README.md").write_text(
        "---\nkind: stage\ntitle: Alignment\ntags: [unterminated list\n---\nbody\n",
        encoding="utf-8",
    )

    report = run_checks(root)

    assert {f.id for f in report.findings} == {RULE_FRONTMATTER}


def test_rule1_illegal_status_is_flagged(tmp_path: Path) -> None:
    root = _project(tmp_path)
    stage = create_stage(root, "Alignment", created=date.today())
    _set_fields(stage / "README.md", status="not-a-real-status")

    report = run_checks(root)

    assert {f.id for f in report.findings} == {RULE_FRONTMATTER}


def test_rule1_unknown_kind_is_flagged(tmp_path: Path) -> None:
    root = _project(tmp_path)
    stage = create_stage(root, "Alignment", created=date.today())
    _set_fields(stage / "README.md", kind="mystery")

    report = run_checks(root)

    assert {f.id for f in report.findings} == {RULE_FRONTMATTER}


def test_rule1_missing_required_field_is_flagged(tmp_path: Path) -> None:
    root = _project(tmp_path)
    stage = create_stage(root, "Alignment", created=date.today())
    fields, body = frontmatter.read(stage / "README.md")
    del fields["script"]
    (stage / "README.md").write_text(frontmatter.render(fields) + body, encoding="utf-8")

    report = run_checks(root)

    assert {f.id for f in report.findings} == {RULE_FRONTMATTER}


# --- rule 2: evidence pointers resolve ------------------------------------------


def test_rule2_broken_script_pointer_is_flagged(tmp_path: Path) -> None:
    root = _project(tmp_path)
    stage = create_stage(root, "Alignment", created=date.today())
    _set_fields(stage / "README.md", script="does_not_exist.sh")

    report = run_checks(root)

    assert {f.id for f in report.findings} == {RULE_EVIDENCE_POINTERS}


def test_rule2_closed_stage_with_empty_log_is_flagged(tmp_path: Path) -> None:
    root = _project(tmp_path)
    stage = create_stage(root, "Alignment", created=date.today())
    _set_fields(stage / "README.md", status="dead-end", log="")

    report = run_checks(root)

    assert {f.id for f in report.findings} == {RULE_EVIDENCE_POINTERS}


def test_rule2_open_question_with_unwritten_log_is_not_flagged(tmp_path: Path) -> None:
    # smairt unit new question pre-fills log: with the filename the probe is
    # expected to write; before it has run, that must not be a finding.
    root = _project(tmp_path)
    create_question(
        root,
        "Does batch correction help?",
        hypothesis="Batch correction removes the batch effect without erasing biology.",
        created=date.today(),
    )

    report = run_checks(root)

    assert report.findings == ()


def test_rule2_reference_unit_paths_resolve_against_project_root(tmp_path: Path) -> None:
    root = _project(tmp_path)
    # Nested under data/ (already a recognized top-level folder) so this test
    # exercises rule 2 (evidence pointers) in isolation from rule 6 (structure
    # drift), which a bare new top-level folder would also trip.
    (root / "data" / "old_analysis").mkdir(parents=True)
    (root / "data" / "old_analysis" / "de_run1.R").write_text("# analysis\n", encoding="utf-8")
    create_question(root, "Old DE run", ref_paths=["data/old_analysis"], created=date.today())

    report = run_checks(root)

    assert report.findings == ()


def test_rule2_reference_unit_broken_path_is_flagged(tmp_path: Path) -> None:
    # DG-5 now validates --ref (and so ref_paths) at creation, so a broken
    # paths: value can only reach rule 2 by hand-editing frontmatter after
    # the fact -- exactly what this test simulates, via _set_fields.
    root = _project(tmp_path)
    (root / "data" / "old_analysis").mkdir(parents=True)
    question = create_question(
        root, "Old DE run", ref_paths=["data/old_analysis"], created=date.today()
    )
    _set_fields(question / "README.md", paths=["does_not_exist_anywhere"])

    report = run_checks(root)

    assert {f.id for f in report.findings} == {RULE_EVIDENCE_POINTERS}
    finding = report.findings[0]
    assert "does_not_exist_anywhere" in finding.message


def test_rule2_absolute_path_in_paths_does_not_silently_resolve(tmp_path: Path) -> None:
    """Regression: `Path("/project") / "/etc/hosts"` evaluates to `Path("/etc/hosts")` --
    pathlib discards the left side of a join when the right side is absolute. An
    absolute `--ref`/`paths:` value that happens to exist somewhere on the machine
    used to pass `smairt check` clean, defeating the documented "paths: resolves
    from the project root" contract with no warning at all.

    DG-5 now rejects an absolute --ref at creation (units.create_question), so
    this simulates the same broken state via a post-creation hand-edit --
    frontmatter check must still catch, not just creation-time validation.
    """
    root = _project(tmp_path)
    outside = tmp_path / "outside_the_project.txt"
    outside.write_text("not part of the project\n", encoding="utf-8")
    (root / "data" / "old_analysis").mkdir(parents=True)
    question = create_question(
        root, "Escaping ref", ref_paths=["data/old_analysis"], created=date.today()
    )
    _set_fields(question / "README.md", paths=[str(outside)])

    report = run_checks(root)

    assert {f.id for f in report.findings} == {RULE_EVIDENCE_POINTERS}
    assert str(outside) in report.findings[0].message


def test_rule2_reference_stage_paths_resolve_against_project_root(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "data" / "old_scripts").mkdir(parents=True)
    create_stage(root, "Old scripts", ref_paths=["data/old_scripts"], created=date.today())

    report = run_checks(root)

    assert report.findings == ()


# --- rule 3: receipt completeness -----------------------------------------------


def test_rule3_receipt_missing_log_is_flagged(tmp_path: Path) -> None:
    root = _project(tmp_path)
    create_question(
        root,
        "Run nf-core rnaseq",
        hypothesis="nf-core/rnaseq reproduces the in-house pipeline's DE calls.",
        receipt=True,
        tool="nf-core/rnaseq",
        tool_version="3.14",
        command="nextflow run nf-core/rnaseq -profile slurm",
        created=date.today(),
    )

    report = run_checks(root)

    assert {f.id for f in report.findings} == {RULE_RECEIPT_COMPLETENESS}


def test_rule3_receipt_missing_tool_version_is_flagged(tmp_path: Path) -> None:
    root = _project(tmp_path)
    question = create_question(
        root,
        "Run nf-core rnaseq",
        hypothesis="nf-core/rnaseq reproduces the in-house pipeline's DE calls.",
        receipt=True,
        tool="nf-core/rnaseq",
        tool_version="3.14",
        command="nextflow run nf-core/rnaseq -profile slurm",
        created=date.today(),
    )
    fields, _body = frontmatter.read(question / "README.md")
    log_path = question / str(fields["log"])
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("log\n", encoding="utf-8")
    _set_fields(question / "README.md", tool_version="")

    report = run_checks(root)

    assert {f.id for f in report.findings} == {RULE_RECEIPT_COMPLETENESS}


# --- rule 4: raw-log immutability -----------------------------------------------


def test_rule4_log_modified_after_commit_is_flagged(tmp_path: Path) -> None:
    root = _project(tmp_path)
    question = create_question(
        root, "Probe", hypothesis="The probe reproduces the known signal.", created=date.today()
    )
    fields, _body = frontmatter.read(question / "README.md")
    log_path = question / str(fields["log"])
    log_path.write_text("first line\n", encoding="utf-8")

    _git(root, "init")
    _git(root, "add", "-A")
    _git(
        root,
        "-c",
        "user.email=test@example.com",
        "-c",
        "user.name=Test",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-m",
        "initial",
    )

    log_path.write_text("first line\nmodified after commit\n", encoding="utf-8")

    report = run_checks(root)

    assert {f.id for f in report.findings} == {RULE_LOG_IMMUTABILITY}


def test_rule4_git_absent_gives_advisory_not_a_finding(tmp_path: Path) -> None:
    root = _project(tmp_path)

    report = run_checks(root)

    assert report.findings == ()
    assert any(s.id == SUGGEST_GIT_UNAVAILABLE for s in report.suggestions)


# --- rule 5: STATUS drift --------------------------------------------------------


def test_rule5_status_drift_names_the_changed_unit(tmp_path: Path) -> None:
    root = _project(tmp_path, created=date(2020, 1, 1))
    create_stage(root, "Alignment", created=date.today())

    report = run_checks(root)

    assert {f.id for f in report.findings} == {RULE_STATUS_DRIFT}
    drift = [f for f in report.findings if f.id == RULE_STATUS_DRIFT]
    assert drift[0].path == "experiments/01_alignment"


# --- rule 6: structure drift ------------------------------------------------------


def test_rule6_loose_file_under_experiments_is_flagged(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "experiments" / "notes.txt").write_text("stray\n", encoding="utf-8")

    report = run_checks(root)

    assert {f.id for f in report.findings} == {RULE_STRUCTURE_DRIFT}


def test_rule6_experiments_readme_is_allowed(tmp_path: Path) -> None:
    root = _project(tmp_path)

    report = run_checks(root)

    assert report.findings == ()


def test_rule6_unknown_top_level_folder_is_flagged(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "mystery").mkdir()

    report = run_checks(root)

    assert {f.id for f in report.findings} == {RULE_STRUCTURE_DRIFT}


def test_rule6_hpc_folder_is_not_flagged(tmp_path: Path) -> None:
    root = _project(tmp_path, hpc=True)

    report = run_checks(root)

    assert report.findings == ()


def test_rule6_adoption_known_folders_are_not_flagged(tmp_path: Path) -> None:
    from smairt.adopt import adopt_project

    root = tmp_path / "existing"
    root.mkdir()
    (root / "old_analysis").mkdir()
    (root / "old_analysis" / "notes.txt").write_text("notes\n", encoding="utf-8")

    adopt_project(
        root,
        name="Adopted",
        researcher="Ada Lovelace",
        description="An adopted project.",
        harness=Harness.none,
        created=date.today(),
        scaffold_version="0.0.0-test",
    )

    report = run_checks(root)

    assert report.findings == ()


def test_rule6_folder_added_after_adoption_is_still_flagged(tmp_path: Path) -> None:
    from smairt.adopt import adopt_project

    root = tmp_path / "existing"
    root.mkdir()
    (root / "old_analysis").mkdir()

    adopt_project(
        root,
        name="Adopted",
        researcher="Ada Lovelace",
        description="An adopted project.",
        harness=Harness.none,
        created=date.today(),
        scaffold_version="0.0.0-test",
    )
    (root / "new_after_adoption").mkdir()

    report = run_checks(root)

    assert {f.id for f in report.findings} == {RULE_STRUCTURE_DRIFT}
    assert any(f.path == "new_after_adoption" for f in report.findings)


# --- rule 7: closed-question completeness -----------------------------------------


def test_rule7_closed_question_without_verdict_is_flagged(tmp_path: Path) -> None:
    root = _project(tmp_path)
    question = create_question(
        root, "Does X help?", hypothesis="X improves the outcome.", created=date.today()
    )
    fields, body = frontmatter.read(question / "README.md")
    log_rel = str(fields["log"])
    (question / log_rel).write_text("log\n", encoding="utf-8")
    body = body.replace(
        "## Analysis plan\n\n", "## Analysis plan\n\nCompare X against control; z-test.\n\n"
    )
    fields["status"] = "supported"
    fields["script"] = "out"  # existing pointer, so rule 2 stays silent
    (question / "README.md").write_text(frontmatter.render(fields) + body, encoding="utf-8")

    report = run_checks(root)

    assert {f.id for f in report.findings} == {RULE_CLOSED_QUESTION}


def test_rule7_closed_question_with_verdict_is_not_flagged(tmp_path: Path) -> None:
    root = _project(tmp_path)
    question = create_question(
        root, "Does X help?", hypothesis="X improves the outcome.", created=date.today()
    )
    fields, body = frontmatter.read(question / "README.md")
    log_rel = str(fields["log"])
    (question / log_rel).write_text("log\n", encoding="utf-8")
    body = body.replace(
        "## Analysis plan\n\n", "## Analysis plan\n\nCompare X against control; z-test.\n\n"
    )
    fields["status"] = "supported"
    fields["script"] = "out"
    fields["verdict"] = "Confirmed: X helps."
    (question / "README.md").write_text(frontmatter.render(fields) + body, encoding="utf-8")

    report = run_checks(root)

    assert report.findings == ()


# --- rule 8: prompted_by resolves --------------------------------------------------


def test_rule8_dangling_prompted_by_is_flagged(tmp_path: Path) -> None:
    root = _project(tmp_path)
    question = create_question(
        root,
        "Why is signal low",
        hypothesis="Signal is low because of a batch effect.",
        created=date.today(),
    )
    _set_fields(question / "README.md", prompted_by="2020-01-01_does-not-exist")

    report = run_checks(root)

    assert {f.id for f in report.findings} == {RULE_PROMPTED_BY}
    finding = report.findings[0]
    assert "2020-01-01_does-not-exist" in finding.message


def test_rule8_absolute_prompted_by_does_not_silently_resolve(tmp_path: Path) -> None:
    """Same pathlib-join escape as rule 2's absolute `paths:` case (see
    test_rule2_absolute_path_in_paths_does_not_silently_resolve), applied to
    `prompted_by:` -- an absolute value must never be treated as resolved,
    even if it happens to name something real on the machine."""
    root = _project(tmp_path)
    question = create_question(
        root,
        "Why is signal low",
        hypothesis="Signal is low because of a batch effect.",
        created=date.today(),
    )
    _set_fields(question / "README.md", prompted_by=str(tmp_path))

    report = run_checks(root)

    assert {f.id for f in report.findings} == {RULE_PROMPTED_BY}


def test_rule8_prompted_by_resolving_to_a_real_unit_is_not_flagged(tmp_path: Path) -> None:
    root = _project(tmp_path)
    origin = create_question(
        root, "Why is signal low", hypothesis="Signal is low because of a batch effect."
    )
    create_question(
        root,
        "Does batch correction fix the low signal",
        hypothesis="Batch correction restores the expected signal level.",
        prompted_by=origin.name,
        created=date.today(),
    )

    report = run_checks(root)

    assert report.findings == ()


def test_rule8_prompted_by_pointing_at_a_folder_with_no_readme_is_flagged(tmp_path: Path) -> None:
    # A bare folder under experiments/ (no README.md of its own) isn't "a real
    # unit" -- the same standard rule SMAIRT002 already holds paths: to. That
    # same bare folder is also exactly what rule SMAIRT012 (DG-2) exists to
    # flag, so this fixture legitimately trips both rules at once.
    root = _project(tmp_path)
    (root / "experiments" / "2026-01-01_not-a-real-unit").mkdir(parents=True)
    question = create_question(
        root,
        "Follow-up",
        hypothesis="The follow-up claim holds.",
        created=date.today(),
    )
    _set_fields(question / "README.md", prompted_by="2026-01-01_not-a-real-unit")

    report = run_checks(root)

    assert {f.id for f in report.findings} == {RULE_PROMPTED_BY, RULE_MISSING_README}


def test_rule8_unset_prompted_by_is_never_flagged(tmp_path: Path) -> None:
    # Nothing ever requires prompted_by: -- an absent field must stay silent.
    root = _project(tmp_path)
    create_question(root, "Plain question", hypothesis="Plain claim.", created=date.today())

    report = run_checks(root)

    assert not any(f.id == RULE_PROMPTED_BY for f in report.findings)


# --- rule 9: hypothesis is non-empty ------------------------------------------------


def test_rule9_empty_hypothesis_is_flagged(tmp_path: Path) -> None:
    root = _project(tmp_path)
    create_question(root, "Does X help?", created=date.today())

    report = run_checks(root)

    assert {f.id for f in report.findings} == {RULE_HYPOTHESIS_NONEMPTY}


def test_rule9_empty_hypothesis_is_flagged_even_while_open(tmp_path: Path) -> None:
    # The rule is not gated on status -- catching a blank claim only at close
    # would let it get written after the result is already known.
    root = _project(tmp_path)
    question = create_question(root, "Does X help?", created=date.today())
    fields, _body = frontmatter.read(question / "README.md")
    assert fields["status"] == "open"

    report = run_checks(root)

    assert RULE_HYPOTHESIS_NONEMPTY in {f.id for f in report.findings}


def test_rule9_reference_question_is_exempt_from_the_hypothesis_check(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "data" / "old_analysis").mkdir(parents=True)

    create_question(root, "Old DE run", ref_paths=["data/old_analysis"], created=date.today())

    report = run_checks(root)

    assert not any(f.id == RULE_HYPOTHESIS_NONEMPTY for f in report.findings)


def test_rule9_missing_hypothesis_key_does_not_double_report_with_rule1(tmp_path: Path) -> None:
    root = _project(tmp_path)
    question = create_question(
        root, "Does X help?", hypothesis="X improves the outcome.", created=date.today()
    )
    fields, body = frontmatter.read(question / "README.md")
    del fields["hypothesis"]
    (question / "README.md").write_text(frontmatter.render(fields) + body, encoding="utf-8")

    report = run_checks(root)

    # SMAIRT001 (missing required field) fires; SMAIRT009 stays silent rather
    # than reporting the same defect a second time.
    assert {f.id for f in report.findings} == {RULE_FRONTMATTER}


# --- rule 10: closed question needs a non-empty Analysis plan ----------------------


def test_rule10_closed_question_with_empty_analysis_plan_is_flagged(tmp_path: Path) -> None:
    root = _project(tmp_path)
    question = create_question(
        root, "Does X help?", hypothesis="X improves the outcome.", created=date.today()
    )
    fields, body = frontmatter.read(question / "README.md")
    log_rel = str(fields["log"])
    (question / log_rel).write_text("log\n", encoding="utf-8")
    fields["status"] = "supported"
    fields["script"] = "out"
    fields["verdict"] = "Confirmed: X helps."
    (question / "README.md").write_text(frontmatter.render(fields) + body, encoding="utf-8")

    report = run_checks(root)

    assert {f.id for f in report.findings} == {RULE_ANALYSIS_PLAN}


def test_rule10_renamed_analysis_plan_heading_gets_a_different_message_than_empty(
    tmp_path: Path,
) -> None:
    """Regression: a hand-renamed '## Analysis plan' heading (with real content
    underneath) used to get the exact same "requires a non-empty ... section"
    message a genuinely empty section gets -- actively misleading, since the
    researcher can see their own paragraph right there. The two cases must
    read differently: "no such heading" vs. "heading found, body empty"."""
    root = _project(tmp_path)
    question = create_question(
        root, "Does X help?", hypothesis="X improves the outcome.", created=date.today()
    )
    fields, body = frontmatter.read(question / "README.md")
    log_rel = str(fields["log"])
    (question / log_rel).write_text("log\n", encoding="utf-8")
    fields["status"] = "supported"
    fields["script"] = "out"
    fields["verdict"] = "Confirmed: X helps."
    # Rename the heading itself (not just its content) and put real prose
    # directly under the renamed heading -- exactly the walk's reproduction.
    renamed_body = body.replace(
        "## Analysis plan\n\n", "## Analysis Approach (renamed)\n\nWe did the thing.\n\n"
    )
    assert "We did the thing." in renamed_body  # sanity: the replace actually matched
    (question / "README.md").write_text(frontmatter.render(fields) + renamed_body, encoding="utf-8")

    report = run_checks(root)

    assert {f.id for f in report.findings} == {RULE_ANALYSIS_PLAN}
    message = report.findings[0].message
    assert "no heading with that exact text was found" in message
    assert "non-empty" not in message


def test_rule10_closed_question_with_analysis_plan_filled_is_not_flagged(tmp_path: Path) -> None:
    root = _project(tmp_path)
    question = create_question(
        root, "Does X help?", hypothesis="X improves the outcome.", created=date.today()
    )
    fields, body = frontmatter.read(question / "README.md")
    log_rel = str(fields["log"])
    (question / log_rel).write_text("log\n", encoding="utf-8")
    body = body.replace(
        "## Analysis plan\n\n", "## Analysis plan\n\nCompare X against control; z-test.\n\n"
    )
    fields["status"] = "supported"
    fields["script"] = "out"
    fields["verdict"] = "Confirmed: X helps."
    (question / "README.md").write_text(frontmatter.render(fields) + body, encoding="utf-8")

    report = run_checks(root)

    assert report.findings == ()


def test_rule10_open_question_with_empty_analysis_plan_is_not_flagged(tmp_path: Path) -> None:
    # Required at close, not at creation -- a hard gate at creation would
    # push researchers back toward mkdir-ing units by hand.
    root = _project(tmp_path)
    create_question(
        root, "Does X help?", hypothesis="X improves the outcome.", created=date.today()
    )

    report = run_checks(root)

    assert not any(f.id == RULE_ANALYSIS_PLAN for f in report.findings)


def test_rule10_reference_question_is_exempt_even_when_closed(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "data" / "old_analysis").mkdir(parents=True)
    question = create_question(
        root, "Old DE run", ref_paths=["data/old_analysis"], created=date.today()
    )
    _set_fields(question / "README.md", status="supported", verdict="Confirmed by the old run.")

    report = run_checks(root)

    assert not any(f.id == RULE_ANALYSIS_PLAN for f in report.findings)


# --- rule 11: growth suggestions (advisory channel) --------------------------------


def test_rule8_suggests_hpc_when_slurm_content_found_without_hpc_folder(tmp_path: Path) -> None:
    root = _project(tmp_path)
    stage = create_stage(root, "Alignment", created=date.today())
    (stage / "out" / "submit.sh").write_text(
        "#!/bin/bash\n#SBATCH --job-name=x\nsbatch other.sh\n", encoding="utf-8"
    )

    report = run_checks(root)

    assert report.findings == ()
    assert any(s.id == SUGGEST_HPC for s in report.suggestions)


def test_rule8_suggests_grouping_when_three_questions_share_a_leading_word(
    tmp_path: Path,
) -> None:
    root = _project(tmp_path)
    create_question(
        root,
        "Replicate3 pca check",
        hypothesis="Replicate 3 separates from the others on PCA.",
        created=date(2026, 1, 1),
    )
    create_question(
        root,
        "Replicate3 clustering check",
        hypothesis="Replicate 3 forms its own cluster.",
        created=date(2026, 1, 2),
    )
    create_question(
        root,
        "Replicate3 outlier check",
        hypothesis="Replicate 3 is a statistical outlier by distance from centroid.",
        created=date(2026, 1, 3),
    )

    report = run_checks(root)

    assert report.findings == ()
    assert any(s.id == SUGGEST_GROUPING for s in report.suggestions)


def test_rule8_suggests_paper_overlay_when_status_mentions_paper_words(tmp_path: Path) -> None:
    root = _project(tmp_path, paper=True)

    report = run_checks(root)

    assert report.findings == ()
    assert any(s.id == SUGGEST_PAPER_OVERLAY for s in report.suggestions)


def test_rule8_suggests_dataset_locations_for_a_data_subfolder_with_no_readme(
    tmp_path: Path,
) -> None:
    root = _project(tmp_path)
    (root / "data" / "handmade").mkdir()

    report = run_checks(root)

    assert report.findings == ()
    assert any(s.id == SUGGEST_DATASET_LOCATIONS for s in report.suggestions)


def test_rule8_suggests_dataset_locations_for_a_readme_with_no_locations_field(
    tmp_path: Path,
) -> None:
    root = _project(tmp_path)
    handmade = root / "data" / "handmade"
    handmade.mkdir()
    (handmade / "README.md").write_text(
        frontmatter.render({"dataset": "handmade"}) + "\nNo locations recorded.\n",
        encoding="utf-8",
    )

    report = run_checks(root)

    assert report.findings == ()
    assert any(s.id == SUGGEST_DATASET_LOCATIONS for s in report.suggestions)


def test_rule8_does_not_suggest_dataset_locations_for_a_dataset_created_by_smairt_data_new(
    tmp_path: Path,
) -> None:
    root = _project(tmp_path)
    create_dataset(root, "Reads")

    report = run_checks(root)

    assert report.findings == ()
    assert not any(s.id == SUGGEST_DATASET_LOCATIONS for s in report.suggestions)


def test_freshly_created_dataset_leaves_smairt_check_completely_clean(tmp_path: Path) -> None:
    # SUGGEST_GIT_UNAVAILABLE still fires here (create_project alone, unlike `smairt
    # new`, never runs `git init`) -- that suggestion is orthogonal to this feature.
    # What this test actually confirms is the SMAIRT105 acceptance criterion: a
    # dataset made via `smairt data new` is never itself flagged as missing locations.
    root = _project(tmp_path)
    create_dataset(root, "Reads")

    report = run_checks(root)

    assert report.findings == ()
    assert not any(s.id == SUGGEST_DATASET_LOCATIONS for s in report.suggestions)


# --- rule SMAIRT011: project identity (smairt.yaml) -----------------------------


def test_rule11_missing_name_field_is_flagged_by_name(tmp_path: Path) -> None:
    root = _project(tmp_path)
    config = yaml.safe_load((root / "smairt.yaml").read_text())
    del config["name"]
    (root / "smairt.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")

    report = run_checks(root)

    assert {f.id for f in report.findings} == {RULE_PROJECT_CONFIG}
    message = report.findings[0].message
    assert "name:" in message
    assert "A correct smairt.yaml looks like this" in message


def test_rule11_empty_smairt_yaml_reports_every_missing_field_in_one_finding(
    tmp_path: Path,
) -> None:
    root = _project(tmp_path)
    (root / "smairt.yaml").write_text("", encoding="utf-8")

    report = run_checks(root)

    assert len(report.findings) == 1
    finding = report.findings[0]
    assert finding.id == RULE_PROJECT_CONFIG
    assert finding.path == "smairt.yaml"
    assert "empty" in finding.message
    assert "A correct smairt.yaml looks like this" in finding.message


def test_rule11_yaml_list_instead_of_mapping_is_flagged(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "smairt.yaml").write_text("- a\n- b\n", encoding="utf-8")

    report = run_checks(root)

    assert {f.id for f in report.findings} == {RULE_PROJECT_CONFIG}
    assert "mapping" in report.findings[0].message


def test_rule11_blank_researcher_field_is_flagged(tmp_path: Path) -> None:
    root = _project(tmp_path)
    config = yaml.safe_load((root / "smairt.yaml").read_text())
    config["researcher"] = "   "
    (root / "smairt.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")

    report = run_checks(root)

    assert {f.id for f in report.findings} == {RULE_PROJECT_CONFIG}
    assert "researcher:" in report.findings[0].message


def test_rule11_missing_multiple_fields_names_all_of_them_in_one_finding(
    tmp_path: Path,
) -> None:
    root = _project(tmp_path)
    config = yaml.safe_load((root / "smairt.yaml").read_text())
    del config["name"]
    del config["description"]
    (root / "smairt.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")

    report = run_checks(root)

    assert {f.id for f in report.findings} == {RULE_PROJECT_CONFIG}
    message = report.findings[0].message
    assert "name:" in message
    assert "description:" in message
    # One finding, one copy of the example -- not one per field.
    assert message.count("A correct smairt.yaml looks like this") == 1


def test_rule11_a_normal_freshly_created_project_is_never_flagged(tmp_path: Path) -> None:
    root = _project(tmp_path)

    report = run_checks(root)

    assert not any(f.id == RULE_PROJECT_CONFIG for f in report.findings)


# --- rule SMAIRT012: README-less unit folder (DG-2) -----------------------------


def test_rule12_folder_under_experiments_with_no_readme_is_flagged(tmp_path: Path) -> None:
    root = _project(tmp_path)
    folder = root / "experiments" / "2026-08-20_hand-made"
    folder.mkdir(parents=True)
    (folder / "notes.txt").write_text("x", encoding="utf-8")

    report = run_checks(root)

    assert {f.id for f in report.findings} == {RULE_MISSING_README}
    finding = report.findings[0]
    assert finding.severity == WARNING
    assert finding.path == "experiments/2026-08-20_hand-made"
    assert "smairt unit new" in finding.message


def test_rule12_a_real_unit_is_never_flagged(tmp_path: Path) -> None:
    root = _project(tmp_path)
    create_stage(root, "Alignment", created=date.today())

    report = run_checks(root)

    assert not any(f.id == RULE_MISSING_README for f in report.findings)


def test_rule12_a_loose_file_directly_under_experiments_is_not_double_flagged(
    tmp_path: Path,
) -> None:
    # A loose FILE (not a folder) is SMAIRT006's job, not SMAIRT012's -- the
    # two rules must not both fire on the same entry.
    root = _project(tmp_path)
    (root / "experiments" / "stray.txt").write_text("x", encoding="utf-8")

    report = run_checks(root)

    assert {f.id for f in report.findings} == {RULE_STRUCTURE_DRIFT}


def test_rule12_a_dot_prefixed_folder_is_not_flagged(tmp_path: Path) -> None:
    # A hidden folder (an editor/tool artifact like .ipynb_checkpoints/) is
    # not a researcher's untracked work -- flagging it would be noise, the
    # same reasoning SMAIRT006's top-level scan already applies.
    root = _project(tmp_path)
    hidden = root / "experiments" / ".ipynb_checkpoints"
    hidden.mkdir()
    (hidden / "scratch.ipynb").write_text("{}", encoding="utf-8")

    report = run_checks(root)

    assert not any(f.id == RULE_MISSING_README for f in report.findings)


# --- rule SMAIRT006 sharpening: nested SMAIRT project (DG-3) --------------------


def test_rule6_nested_smairt_project_gets_a_specific_message(tmp_path: Path) -> None:
    root = _project(tmp_path)
    nested = root / "inner_project"
    create_project(
        nested,
        name="Inner",
        researcher="Ada Lovelace",
        description="Nested inside the outer project.",
        harness=Harness.none,
        created=date.today(),
        scaffold_version="0.0.0-test",
    )

    report = run_checks(root)

    findings = [
        f for f in report.findings if f.id == RULE_STRUCTURE_DRIFT and f.path == "inner_project"
    ]
    assert len(findings) == 1
    assert "is itself a SMAIRT project" in findings[0].message
    assert "smairt.yaml" in findings[0].message


def test_rule6_unknown_folder_without_smairt_yaml_keeps_the_generic_message(
    tmp_path: Path,
) -> None:
    root = _project(tmp_path)
    (root / "just_a_folder").mkdir()

    report = run_checks(root)

    findings = [f for f in report.findings if f.id == RULE_STRUCTURE_DRIFT]
    assert len(findings) == 1
    assert "is itself a SMAIRT project" not in findings[0].message
    assert "not part of the known scaffold" in findings[0].message


# --- rule SMAIRT013: prompted_by cycles (DG-4) -----------------------------------


def _linked_question(root: Path, title: str, *, prompted_by: str | None = None) -> Path:
    return create_question(
        root,
        title,
        hypothesis=f"{title} holds.",
        prompted_by=prompted_by,
        created=date.today(),
    )


def test_rule13_two_unit_cycle_is_flagged_naming_both_units(tmp_path: Path) -> None:
    root = _project(tmp_path)
    q1 = create_question(root, "Q1", hypothesis="H1.", created=date(2026, 1, 1))
    q2 = create_question(
        root, "Q2", hypothesis="H2.", created=date(2026, 1, 2), prompted_by=q1.name
    )
    # Hand-edit Q1 to close the loop: Q1 <- Q2 <- Q1.
    _set_fields(q1 / "README.md", prompted_by=q2.name)

    report = run_checks(root)

    cycle_findings = [f for f in report.findings if f.id == RULE_PROMPTED_BY_CYCLE]
    assert len(cycle_findings) == 1
    message = cycle_findings[0].message
    assert q1.name in message
    assert q2.name in message
    assert cycle_findings[0].severity == ERROR


def test_rule13_five_unit_cycle_is_detected_and_matches_the_friction_walk_shape(
    tmp_path: Path,
) -> None:
    # Reproduces DG-4's exact setup: a 5-level --from chain closed into a
    # loop by hand-editing the first unit's frontmatter (Q1->Q2->Q3->Q4->Q5->Q1).
    root = _project(tmp_path)
    q1 = _linked_question(root, "Q1")
    q2 = _linked_question(root, "Q2", prompted_by=q1.name)
    q3 = _linked_question(root, "Q3", prompted_by=q2.name)
    q4 = _linked_question(root, "Q4", prompted_by=q3.name)
    q5 = _linked_question(root, "Q5", prompted_by=q4.name)
    _set_fields(q1 / "README.md", prompted_by=q5.name)

    report = run_checks(root)

    cycle_findings = [f for f in report.findings if f.id == RULE_PROMPTED_BY_CYCLE]
    assert len(cycle_findings) == 1
    message = cycle_findings[0].message
    for unit in (q1, q2, q3, q4, q5):
        assert unit.name in message


def test_rule13_a_dangling_prompted_by_is_not_treated_as_a_cycle(tmp_path: Path) -> None:
    # A link that doesn't resolve is SMAIRT008's finding, not a cycle
    # candidate -- the two rules must partition the field's problems, not
    # double-report the same root cause.
    root = _project(tmp_path)
    question = create_question(root, "Q1", hypothesis="H1.", created=date.today())
    _set_fields(question / "README.md", prompted_by="does-not-exist")

    report = run_checks(root)

    assert {f.id for f in report.findings} == {RULE_PROMPTED_BY}


def test_rule13_a_self_referencing_prompted_by_is_a_degenerate_cycle(tmp_path: Path) -> None:
    # A unit naming ITSELF as prompted_by "resolves" by SMAIRT008's own rule
    # (its own README.md genuinely exists at that path), so SMAIRT008 alone
    # never catches this -- it is exactly as impossible in real work as any
    # longer loop ("a question prompted by itself"), just a length-1 cycle,
    # so rule SMAIRT013 must catch it even though SMAIRT008 doesn't.
    root = _project(tmp_path)
    question = create_question(root, "Q1", hypothesis="H1.", created=date.today())
    _set_fields(question / "README.md", prompted_by=question.name)

    report = run_checks(root)

    assert {f.id for f in report.findings} == {RULE_PROMPTED_BY_CYCLE}
    assert question.name in report.findings[0].message


def test_rule13_a_normal_lineage_chain_is_never_flagged(tmp_path: Path) -> None:
    root = _project(tmp_path)
    q1 = _linked_question(root, "Q1")
    _linked_question(root, "Q2", prompted_by=q1.name)

    report = run_checks(root)

    assert not any(f.id == RULE_PROMPTED_BY_CYCLE for f in report.findings)


def test_rule13_cyclic_project_does_not_hang_check_status_or_index(tmp_path: Path) -> None:
    """Regression for DG-4's own verification: the friction walk confirmed a
    hand-made prompted_by: cycle never hangs or crashes `check`/`status`/
    `index`, under a hard 15-second subprocess timeout. This rule ADDS
    detection on top of that; it must not regress the "never hangs" part."""
    root = _project(tmp_path)
    q1 = _linked_question(root, "Q1")
    q2 = _linked_question(root, "Q2", prompted_by=q1.name)
    q3 = _linked_question(root, "Q3", prompted_by=q2.name)
    _set_fields(q1 / "README.md", prompted_by=q3.name)

    for command in ("check", "status", "index"):
        result = subprocess.run(
            [sys.executable, "-c", "from smairt.cli import main; main()", command],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode in (0, 1), (command, result.stdout, result.stderr)


# --- output rendering --------------------------------------------------------------


def test_to_json_reflects_findings_and_exit_code(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "experiments" / "stray.txt").write_text("x", encoding="utf-8")

    report = run_checks(root)
    payload = to_json(report)

    assert len(payload["findings"]) == len(report.findings)
    assert payload["summary"]["exit_code"] == 1


def test_render_human_includes_finding_id_and_path(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "experiments" / "stray.txt").write_text("x", encoding="utf-8")

    report = run_checks(root)
    text = render_human(report)

    assert RULE_STRUCTURE_DRIFT in text
    assert "experiments/stray.txt" in text


def test_rule2_relative_path_climbing_out_of_the_project_does_not_silently_resolve(
    tmp_path: Path,
) -> None:
    """Regression: a `../`-escaping RELATIVE pointer is the same mistake as an absolute one.

    The absolute-path guard above only catches targets that look like escapes.
    A relative target with enough `../` to climb out of the project is not
    absolute, so it slipped past — and if it landed on a real file it passed
    `smairt check` completely clean while pointing at something the project
    does not contain. Both spellings have to be caught.
    """
    root = _project(tmp_path)
    outside = tmp_path / "outside_the_project.txt"
    outside.write_text("not part of the project\n", encoding="utf-8")
    (root / "data" / "old_analysis").mkdir(parents=True)
    question = create_question(
        root, "Climbing ref", ref_paths=["data/old_analysis"], created=date.today()
    )
    climbing = "../" * len(root.resolve().parts) + str(outside.resolve()).lstrip("/")
    _set_fields(question / "README.md", paths=[climbing])

    report = run_checks(root)

    assert {f.id for f in report.findings} == {RULE_EVIDENCE_POINTERS}
    assert climbing in report.findings[0].message
