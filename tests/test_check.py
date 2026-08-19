from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path

from smairt import frontmatter
from smairt.check import (
    RULE_CLOSED_QUESTION,
    RULE_EVIDENCE_POINTERS,
    RULE_FRONTMATTER,
    RULE_LOG_IMMUTABILITY,
    RULE_RECEIPT_COMPLETENESS,
    RULE_STATUS_DRIFT,
    RULE_STRUCTURE_DRIFT,
    SUGGEST_GIT_UNAVAILABLE,
    SUGGEST_GROUPING,
    SUGGEST_HPC,
    SUGGEST_PAPER_OVERLAY,
    render_human,
    run_checks,
    to_json,
)
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
    create_question(root, "Does batch correction help?", created=date.today())

    report = run_checks(root)

    assert report.findings == ()


# --- rule 1: frontmatter schema -------------------------------------------------


def test_rule1_malformed_frontmatter_is_flagged(tmp_path: Path) -> None:
    root = _project(tmp_path)
    stage = create_stage(root, "Alignment", created=date.today())
    (stage / "README.md").write_text("no frontmatter block here\n", encoding="utf-8")

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
    create_question(root, "Does batch correction help?", created=date.today())

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
    root = _project(tmp_path)
    create_question(root, "Old DE run", ref_paths=["does_not_exist_anywhere"], created=date.today())

    report = run_checks(root)

    assert {f.id for f in report.findings} == {RULE_EVIDENCE_POINTERS}
    finding = report.findings[0]
    assert "does_not_exist_anywhere" in finding.message


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
    question = create_question(root, "Probe", created=date.today())
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
    question = create_question(root, "Does X help?", created=date.today())
    fields, body = frontmatter.read(question / "README.md")
    log_rel = str(fields["log"])
    (question / log_rel).write_text("log\n", encoding="utf-8")
    fields["status"] = "supported"
    fields["script"] = "out"  # existing pointer, so rule 2 stays silent
    (question / "README.md").write_text(frontmatter.render(fields) + body, encoding="utf-8")

    report = run_checks(root)

    assert {f.id for f in report.findings} == {RULE_CLOSED_QUESTION}


def test_rule7_closed_question_with_verdict_is_not_flagged(tmp_path: Path) -> None:
    root = _project(tmp_path)
    question = create_question(root, "Does X help?", created=date.today())
    fields, body = frontmatter.read(question / "README.md")
    log_rel = str(fields["log"])
    (question / log_rel).write_text("log\n", encoding="utf-8")
    fields["status"] = "supported"
    fields["script"] = "out"
    fields["verdict"] = "Confirmed: X helps."
    (question / "README.md").write_text(frontmatter.render(fields) + body, encoding="utf-8")

    report = run_checks(root)

    assert report.findings == ()


# --- rule 8: growth suggestions (advisory channel) --------------------------------


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
    create_question(root, "Replicate3 pca check", created=date(2026, 1, 1))
    create_question(root, "Replicate3 clustering check", created=date(2026, 1, 2))
    create_question(root, "Replicate3 outlier check", created=date(2026, 1, 3))

    report = run_checks(root)

    assert report.findings == ()
    assert any(s.id == SUGGEST_GROUPING for s in report.suggestions)


def test_rule8_suggests_paper_overlay_when_status_mentions_paper_words(tmp_path: Path) -> None:
    root = _project(tmp_path, paper=True)

    report = run_checks(root)

    assert report.findings == ()
    assert any(s.id == SUGGEST_PAPER_OVERLAY for s in report.suggestions)


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
