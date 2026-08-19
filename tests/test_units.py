from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from smairt import frontmatter
from smairt.cli import app
from smairt.fsutil import PathExistsError
from smairt.project import Harness, create_project
from smairt.units import (
    QUESTION_REQUIRED_FIELDS,
    QUESTION_STATUSES,
    STAGE_REQUIRED_FIELDS,
    STAGE_STATUSES,
    create_question,
    create_stage,
)

runner = CliRunner()


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    create_project(
        root,
        name="Unit Test Project",
        researcher="Ada Lovelace",
        description="Exercises smairt unit new.",
        harness=Harness.claude_code,
        created=date(2026, 1, 1),
        scaffold_version="0.0.0-test",
    )
    return root


def test_create_stage_numbers_sequentially_and_zero_pads(tmp_path: Path) -> None:
    root = _project(tmp_path)

    first = create_stage(root, "Quality control")
    second = create_stage(root, "Differential expression")

    assert first.name == "01_quality_control"
    assert second.name == "02_differential_expression"


def test_create_stage_writes_standard_subfolders(tmp_path: Path) -> None:
    root = _project(tmp_path)

    stage = create_stage(root, "Alignment")

    assert (stage / "logs").is_dir()
    assert (stage / "out").is_dir()
    assert (stage / "figures").is_dir()


def test_create_stage_readme_has_required_schema_fields_and_legal_status(tmp_path: Path) -> None:
    root = _project(tmp_path)

    stage = create_stage(root, "Alignment", created=date(2026, 1, 5))
    fields, body = frontmatter.read(stage / "README.md")

    for name in STAGE_REQUIRED_FIELDS:
        assert name in fields, name
    assert fields["kind"] == "stage"
    assert fields["status"] in STAGE_STATUSES
    assert fields["created"] == date(2026, 1, 5)
    assert "## Purpose" in body
    assert "## Approach" in body
    assert "## Result" in body


def test_create_question_uses_todays_date_in_the_folder_name(tmp_path: Path) -> None:
    root = _project(tmp_path)

    question = create_question(root, "Does batch correction help?", created=date(2026, 3, 4))

    assert question.name == "2026-03-04_does_batch_correction_help"


def test_create_question_readme_has_required_schema_fields_and_legal_status(
    tmp_path: Path,
) -> None:
    root = _project(tmp_path)

    question = create_question(
        root,
        "Does excluding replicate 3 change results?",
        hypothesis="Excluding replicate 3 sharpens separation.",
        created=date(2026, 2, 2),
    )
    fields, body = frontmatter.read(question / "README.md")

    for name in QUESTION_REQUIRED_FIELDS:
        assert name in fields, name
    assert fields["kind"] == "question"
    assert fields["status"] in QUESTION_STATUSES
    assert fields["date"] == date(2026, 2, 2)
    assert fields["hypothesis"] == "Excluding replicate 3 sharpens separation."
    for heading in (
        "## Why ask this",
        "## What we expected",
        "## What happened",
        "## What it means",
        "## Next",
    ):
        assert heading in body


def test_create_question_without_hypothesis_leaves_it_empty_but_present(tmp_path: Path) -> None:
    root = _project(tmp_path)

    question = create_question(root, "Untitled probe", created=date(2026, 1, 2))
    fields, _ = frontmatter.read(question / "README.md")

    assert fields["hypothesis"] == ""


def test_receipt_variant_adds_tool_fields(tmp_path: Path) -> None:
    root = _project(tmp_path)

    question = create_question(
        root,
        "Run nf-core rnaseq",
        receipt=True,
        tool="nf-core/rnaseq",
        tool_version="3.14",
        command="nextflow run nf-core/rnaseq -profile slurm",
        created=date(2026, 1, 3),
    )
    fields, _ = frontmatter.read(question / "README.md")

    assert fields["tool"] == "nf-core/rnaseq"
    assert fields["tool_version"] == "3.14"
    assert fields["command"] == "nextflow run nf-core/rnaseq -profile slurm"
    assert fields["repo"] == ""


def test_receipt_without_tool_is_rejected(tmp_path: Path) -> None:
    root = _project(tmp_path)

    with pytest.raises(ValueError):
        create_question(root, "Run something", receipt=True, created=date(2026, 1, 3))


def test_create_question_refuses_a_same_day_same_title_duplicate(tmp_path: Path) -> None:
    root = _project(tmp_path)
    create_question(root, "Alignment check", created=date(2026, 1, 5))

    with pytest.raises(PathExistsError):
        create_question(root, "Alignment check", created=date(2026, 1, 5))


def test_cli_unit_new_stage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _project(tmp_path)
    monkeypatch.chdir(root)

    result = runner.invoke(app, ["unit", "new", "stage", "--title", "Alignment"])

    assert result.exit_code == 0, result.output
    assert (root / "experiments" / "01_alignment" / "README.md").is_file()


def test_cli_unit_new_refuses_outside_a_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["unit", "new", "stage", "--title", "Alignment"])

    assert result.exit_code != 0
    assert "not a SMAIRT project" in result.output


def test_cli_unit_new_finds_project_root_from_a_subdirectory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _project(tmp_path)
    monkeypatch.chdir(root / "experiments")

    result = runner.invoke(app, ["unit", "new", "question", "--title", "Nested invocation"])

    assert result.exit_code == 0, result.output


def test_smairt_yaml_is_untouched_by_yaml_dump_quirks_after_unit_creation(tmp_path: Path) -> None:
    # Sanity check that creating units does not disturb the project's identity file.
    root = _project(tmp_path)
    before = (root / "smairt.yaml").read_text()

    create_stage(root, "Alignment", created=date(2026, 1, 5))

    after = (root / "smairt.yaml").read_text()
    assert before == after
    assert yaml.safe_load(after)["schema_version"] == 2
