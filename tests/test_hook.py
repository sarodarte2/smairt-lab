"""Tests for ``smairt hook`` (cli.py): the exit-code adapter harness hooks call.

``report`` always exits 0 so a session-end hook can never wedge a harness in
a failure loop; ``gate`` exits 2 — the block code Claude Code, Codex, and
Cursor all understand — while findings exist. Both are read-only wrappers
over ``smairt check``.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

from smairt.cli import app
from smairt.project import Harness, create_project

runner = CliRunner()


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    create_project(
        root,
        name="Hook Test Project",
        researcher="Ada Lovelace",
        description="Exercises smairt hook.",
        harness=Harness.none,
        created=date(2026, 1, 1),
        scaffold_version="0.0.0-test",
    )
    return root


def test_report_exits_zero_on_a_clean_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(_project(tmp_path))

    result = runner.invoke(app, ["hook", "report"])

    assert result.exit_code == 0, result.output
    assert result.output.strip()  # the findings summary is printed, not swallowed


def test_report_still_exits_zero_when_findings_exist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _project(tmp_path)
    (root / "experiments" / "notes.txt").write_text("stray\n", encoding="utf-8")
    monkeypatch.chdir(root)

    result = runner.invoke(app, ["hook", "report"])

    assert result.exit_code == 0, result.output
    assert "notes.txt" in result.output


def test_gate_exits_zero_on_a_clean_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(_project(tmp_path))

    result = runner.invoke(app, ["hook", "gate"])

    assert result.exit_code == 0, result.output


def test_gate_exits_two_and_reports_on_stderr_when_findings_exist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _project(tmp_path)
    (root / "experiments" / "notes.txt").write_text("stray\n", encoding="utf-8")
    monkeypatch.chdir(root)

    result = runner.invoke(app, ["hook", "gate"])

    assert result.exit_code == 2
    # Stderr is what blocking harnesses relay back to the agent.
    assert "notes.txt" in result.stderr


def test_unknown_mode_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(_project(tmp_path))

    result = runner.invoke(app, ["hook", "block"])

    assert result.exit_code not in (0, 2)
    assert "unknown mode" in result.output + result.stderr


def test_hook_refuses_outside_a_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["hook", "gate"])

    assert result.exit_code not in (0, 2)
    assert "not a SMAIRT project" in result.output + result.stderr
