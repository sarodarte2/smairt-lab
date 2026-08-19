"""Tests for ``smairt adopt`` (src/smairt/adopt.py): wrapping a pre-existing project.

Covers: the contract files it writes, the refusals (empty dir, already a
SMAIRT project, looks like the tool's own checkout), and that it never moves
or touches anything already in the adopted directory.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from smairt.adopt import AdoptResult, NotAdoptableError, adopt_project
from smairt.check import run_checks
from smairt.cli import app
from smairt.project import Harness, create_project

runner = CliRunner()


def _fake_research_project(tmp_path: Path) -> Path:
    """A directory shaped like a real pre-SMAIRT research project: a couple of
    folders holding scripts and outputs, plus a loose top-level file."""
    root = tmp_path / "existing_project"
    root.mkdir()
    (root / "old_analysis").mkdir()
    (root / "old_analysis" / "de_run1.R").write_text(
        "# differential expression, first pass\n", encoding="utf-8"
    )
    (root / "old_analysis" / "results.csv").write_text("gene,logfc\nBRCA1,2.1\n", encoding="utf-8")
    (root / "old_scripts").mkdir()
    (root / "old_scripts" / "helper.sh").write_text("#!/bin/bash\necho hi\n", encoding="utf-8")
    (root / "README.md").write_text("# Existing project\n\nPre-SMAIRT notes.\n", encoding="utf-8")
    return root


def _adopt(root: Path, **overrides: object) -> AdoptResult:
    defaults: dict[str, object] = dict(
        name="Adopted Project",
        researcher="Ada Lovelace",
        description="A pre-existing DE project adopted into SMAIRT.",
        harness=Harness.none,
        created=date(2026, 1, 1),
        scaffold_version="0.0.0-test",
    )
    defaults.update(overrides)
    return adopt_project(root, **defaults)  # type: ignore[arg-type]


# --- happy path -----------------------------------------------------------------


def test_adopt_writes_only_the_contract_files(tmp_path: Path) -> None:
    root = _fake_research_project(tmp_path)

    _adopt(root)

    for expected in ("smairt.yaml", "STATUS.md", "AGENTS.md", "experiments/README.md"):
        assert (root / expected).is_file(), expected
    assert (root / "results" / "INDEX.md").is_file()

    # Adopt does NOT create the scaffold folders that stand in for pre-existing
    # structure, nor a .gitignore (spec: "only the contract files").
    for absent in ("background", "data", "scripts", "hpc", ".gitignore"):
        assert not (root / absent).exists(), absent


def test_adopt_never_modifies_pre_existing_files(tmp_path: Path) -> None:
    root = _fake_research_project(tmp_path)
    before = {
        path: (path.read_text(encoding="utf-8"), path.stat().st_mtime_ns)
        for path in root.rglob("*")
        if path.is_file()
    }

    _adopt(root)

    for path, (content, mtime) in before.items():
        assert path.read_text(encoding="utf-8") == content, path
        assert path.stat().st_mtime_ns == mtime, path


def test_adopt_records_known_folders_in_smairt_yaml(tmp_path: Path) -> None:
    root = _fake_research_project(tmp_path)

    _adopt(root, created=date(2026, 3, 4))

    config = yaml.safe_load((root / "smairt.yaml").read_text(encoding="utf-8"))
    assert config["adoption"] == {
        "adopted": True,
        "date": date(2026, 3, 4),
        "known_folders": ["old_analysis", "old_scripts"],
    }


def test_adopt_status_md_is_seeded_per_spec(tmp_path: Path) -> None:
    root = _fake_research_project(tmp_path)

    _adopt(root, description="Adopted DE project.")

    status = (root / "STATUS.md").read_text(encoding="utf-8")
    assert "Adopted DE project." in status
    assert "smairt-adopt skill" in status
    assert "create reference units" in status


def test_adopted_project_passes_check_immediately(tmp_path: Path) -> None:
    root = _fake_research_project(tmp_path)

    _adopt(root)
    report = run_checks(root)

    assert report.findings == (), report.findings
    assert report.exit_code == 0


def test_adopted_project_new_folder_after_adoption_still_flagged(tmp_path: Path) -> None:
    root = _fake_research_project(tmp_path)
    _adopt(root)

    (root / "brand_new_folder").mkdir()
    report = run_checks(root)

    assert any(f.path == "brand_new_folder" for f in report.findings)


def test_adopt_with_claude_code_harness_writes_bridge_and_hooks(tmp_path: Path) -> None:
    root = _fake_research_project(tmp_path)

    result = _adopt(root, harness=Harness.claude_code)

    assert (root / "CLAUDE.md").is_file()
    assert (root / ".claude" / "settings.json").is_file()
    assert result.connect_result is not None
    assert ".claude/settings.json" in result.connect_result.written


def test_adopt_with_harness_none_writes_no_bridge(tmp_path: Path) -> None:
    root = _fake_research_project(tmp_path)

    result = _adopt(root, harness=Harness.none)

    assert not (root / "CLAUDE.md").exists()
    assert result.connect_result is None


# --- refusals ---------------------------------------------------------------------


def test_adopt_refuses_an_existing_smairt_project(tmp_path: Path) -> None:
    root = tmp_path / "project"
    create_project(
        root,
        name="Already SMAIRT",
        researcher="Ada Lovelace",
        description="Already a SMAIRT project.",
        harness=Harness.none,
        created=date(2026, 1, 1),
        scaffold_version="0.0.0-test",
    )

    with pytest.raises(NotAdoptableError):
        _adopt(root)


def test_adopt_refuses_an_empty_directory(tmp_path: Path) -> None:
    root = tmp_path / "empty"
    root.mkdir()

    with pytest.raises(NotAdoptableError, match="smairt new"):
        _adopt(root)


def test_adopt_refuses_a_missing_directory(tmp_path: Path) -> None:
    root = tmp_path / "does_not_exist"

    with pytest.raises(NotAdoptableError):
        _adopt(root)


def test_adopt_refuses_a_smairt_tool_checkout(tmp_path: Path) -> None:
    root = tmp_path / "smairt-lab"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        '[project]\nname = "smairt"\nversion = "0.4.0"\n', encoding="utf-8"
    )
    (root / "src").mkdir()

    with pytest.raises(NotAdoptableError):
        _adopt(root)


def test_adopt_rejects_empty_description(tmp_path: Path) -> None:
    root = _fake_research_project(tmp_path)

    with pytest.raises(ValueError):
        _adopt(root, description="   ")


# --- respecting existing contract-shaped files -------------------------------------


def test_adopt_warns_about_and_does_not_touch_an_existing_agents_md(tmp_path: Path) -> None:
    root = _fake_research_project(tmp_path)
    researcher_agents = "# AGENTS.md\n\nOur own house rules, written before SMAIRT existed.\n"
    (root / "AGENTS.md").write_text(researcher_agents, encoding="utf-8")

    result = _adopt(root)

    assert any("AGENTS.md" in warning for warning in result.warned)
    assert (root / "AGENTS.md").read_text(encoding="utf-8") == researcher_agents


# --- CLI ----------------------------------------------------------------------------


def test_cli_adopt_non_interactive(tmp_path: Path) -> None:
    root = _fake_research_project(tmp_path)

    result = runner.invoke(
        app,
        [
            "adopt",
            "--name",
            "CLI Adopted Project",
            "--researcher",
            "Ada Lovelace",
            "--description",
            "Exercises smairt adopt end to end.",
            "--path",
            str(root),
            "--harness",
            "none",
        ],
        input="",
    )

    assert result.exit_code == 0, result.output
    assert (root / "smairt.yaml").is_file()
    config = yaml.safe_load((root / "smairt.yaml").read_text())
    assert config["name"] == "CLI Adopted Project"
    assert config["adoption"]["known_folders"] == ["old_analysis", "old_scripts"]


def test_cli_adopt_refuses_an_existing_smairt_project(tmp_path: Path) -> None:
    root = tmp_path / "project"
    create_project(
        root,
        name="Already SMAIRT",
        researcher="Ada Lovelace",
        description="Already a SMAIRT project.",
        harness=Harness.none,
        created=date(2026, 1, 1),
        scaffold_version="0.0.0-test",
    )

    result = runner.invoke(
        app,
        [
            "adopt",
            "--name",
            "X",
            "--researcher",
            "Y",
            "--description",
            "Z",
            "--path",
            str(root),
            "--harness",
            "none",
        ],
        input="",
    )

    assert result.exit_code != 0
    assert "smairt.yaml" in result.output


def test_cli_adopt_refuses_an_empty_directory(tmp_path: Path) -> None:
    root = tmp_path / "empty"
    root.mkdir()

    result = runner.invoke(
        app,
        [
            "adopt",
            "--name",
            "X",
            "--researcher",
            "Y",
            "--description",
            "Z",
            "--path",
            str(root),
            "--harness",
            "none",
        ],
        input="",
    )

    assert result.exit_code != 0
    assert "smairt new" in result.output
