"""Tests for ``smairt new`` (src/smairt/project.py): the day-one scaffold.

Covers the full set of files/folders create_project() writes, the
write-once refusal on a second run, and the rendered content of
AGENTS.md/STATUS.md/smairt.yaml.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml

from smairt.fsutil import PathExistsError
from smairt.project import Harness, create_project

GOLDEN_FIXTURE = Path(__file__).parent / "fixtures" / "golden"

TEN_ITEMS = {
    "smairt.yaml",
    "STATUS.md",
    "AGENTS.md",
    "CLAUDE.md",
    ".gitignore",
    "background",
    "data",
    "scripts",
    "experiments",
    "results",
}


def _create(tmp_path: Path, **overrides: object) -> Path:
    root = tmp_path / "project"
    defaults: dict[str, object] = dict(
        name="Test Project",
        researcher="Ada Lovelace",
        description="A project used to exercise smairt new.",
        harness=Harness.claude_code,
        hpc=False,
        paper=False,
        created=date(2026, 1, 1),
        scaffold_version="0.0.0-test",
    )
    defaults.update(overrides)
    create_project(root, **defaults)  # type: ignore[arg-type]
    return root


def test_default_project_has_exactly_the_ten_day_one_items(tmp_path: Path) -> None:
    root = _create(tmp_path)

    assert {entry.name for entry in root.iterdir()} == TEN_ITEMS


def test_smairt_yaml_matches_part_ii_schema(tmp_path: Path) -> None:
    root = _create(tmp_path, harness=Harness.codex)

    config = yaml.safe_load((root / "smairt.yaml").read_text())

    assert config == {
        "schema_version": 2,
        "scaffold_version": "0.0.0-test",
        "name": "Test Project",
        "researcher": "Ada Lovelace",
        "description": "A project used to exercise smairt new.",
        "created": date(2026, 1, 1),
        "harnesses": ["codex"],
        "settings": {"strict_hooks": False},
    }


def test_harness_none_records_an_empty_harness_list(tmp_path: Path) -> None:
    root = _create(tmp_path, harness=Harness.none)

    config = yaml.safe_load((root / "smairt.yaml").read_text())

    assert config["harnesses"] == []


def test_generation_never_overwrites_an_existing_file(tmp_path: Path) -> None:
    root = tmp_path / "project"
    _create(tmp_path)

    with pytest.raises(PathExistsError):
        create_project(
            root,
            name="Test Project",
            researcher="Ada Lovelace",
            description="second call",
            created=date(2026, 1, 1),
        )
    # The original file must be untouched by the failed second call.
    assert "second call" not in (root / "STATUS.md").read_text()


def test_empty_description_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        _create(tmp_path, description="   ")


def test_empty_researcher_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        _create(tmp_path, researcher="  ")


def test_hpc_opt_in_adds_hpc_folder_with_readme_and_template(tmp_path: Path) -> None:
    root = _create(tmp_path, hpc=True)

    assert (root / "hpc" / "README.md").is_file()
    template = (root / "hpc" / "submit.slurm.example").read_text()
    assert "#SBATCH" in template


def test_hpc_opt_out_by_default_produces_no_hpc_folder(tmp_path: Path) -> None:
    root = _create(tmp_path)

    assert not (root / "hpc").exists()


def test_paper_opt_in_adds_a_status_open_question_and_nothing_else(tmp_path: Path) -> None:
    with_paper = _create(tmp_path / "with_paper", hpc=False, paper=True)
    without_paper = _create(tmp_path / "without_paper", hpc=False, paper=False)

    with_status = (with_paper / "STATUS.md").read_text()
    without_status = (without_paper / "STATUS.md").read_text()

    assert "paper" in with_status.lower()
    assert "paper" not in without_status.lower()
    # No other file changes: the opt-in only touches STATUS.md's open questions.
    with_files = {p.relative_to(with_paper) for p in with_paper.rglob("*") if p.is_file()}
    without_files = {p.relative_to(without_paper) for p in without_paper.rglob("*") if p.is_file()}
    assert with_files == without_files


def test_agents_md_is_under_the_120_line_budget(tmp_path: Path) -> None:
    root = _create(tmp_path)

    agents_lines = len((root / "AGENTS.md").read_text().splitlines())

    assert agents_lines <= 120, f"AGENTS.md is {agents_lines} lines"


def test_other_generated_day_one_prose_is_under_the_150_line_budget(tmp_path: Path) -> None:
    root = _create(tmp_path)

    markdown_files = sorted(p for p in root.rglob("*.md") if p.name != "AGENTS.md")
    total_lines = sum(len(path.read_text().splitlines()) for path in markdown_files)

    assert total_lines < 150, f"{total_lines} lines across {[str(p) for p in markdown_files]}"


def test_matches_golden_fixture_byte_for_byte(tmp_path: Path) -> None:
    root = tmp_path / "golden"
    create_project(
        root,
        name="Golden Project",
        researcher="Ada Lovelace",
        description="A golden fixture project used to catch scaffold drift.",
        harness=Harness.claude_code,
        hpc=False,
        paper=False,
        created=date(2026, 1, 1),
        scaffold_version="0.0.0-golden",
    )

    generated = _read_tree(root)
    golden = _read_tree(GOLDEN_FIXTURE)

    assert generated == golden


def _read_tree(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }
