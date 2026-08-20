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


def _write_broken_yaml_unit(root: Path) -> None:
    """A unit whose frontmatter delimiters are well-formed but the YAML inside
    them is not -- the exact input that used to crash `run_checks` with a raw
    `yaml.parser.ParserError` (see test_check.py's rule1 regression) rather
    than reporting a finding."""
    unit = root / "experiments" / "01_bad_yaml"
    unit.mkdir(parents=True)
    (unit / "README.md").write_text(
        "---\nkind: stage\ntitle: Bad YAML\ntags: [unterminated list\n---\nbody\n",
        encoding="utf-8",
    )


def test_report_still_exits_zero_when_the_underlying_check_used_to_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exit-code contract regression: `hook report` is documented to ALWAYS exit
    0. Before frontmatter.parse() caught yaml.YAMLError, a project with the
    malformed-YAML-inside-a-block input above made the underlying `run_checks`
    call raise, and the uncaught exception surfaced as exit 1 -- a promise a
    generated hook config depends on ("report" never fails a session-end
    hook), silently broken by any crash the walk could trigger."""
    root = _project(tmp_path)
    _write_broken_yaml_unit(root)
    monkeypatch.chdir(root)

    result = runner.invoke(app, ["hook", "report"])

    assert result.exit_code == 0, result.output + result.stderr
    assert "SMAIRT001" in result.output


def test_gate_exits_two_not_a_crash_exit_when_the_underlying_check_used_to_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same exit-code contract regression as above, for `hook gate`: exit 2 must
    stay reserved for "findings exist, block" -- a bare exit 1 from an
    unhandled crash is indistinguishable from a legitimate non-blocking
    error, and must not leak through in place of the finding it should have
    been."""
    root = _project(tmp_path)
    _write_broken_yaml_unit(root)
    monkeypatch.chdir(root)

    result = runner.invoke(app, ["hook", "gate"])

    assert result.exit_code == 2
    assert "SMAIRT001" in result.stderr


def test_unknown_mode_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(_project(tmp_path))

    result = runner.invoke(app, ["hook", "block"])

    assert result.exit_code not in (0, 2)
    assert "unknown mode" in result.output + result.stderr


def test_hook_refuses_outside_a_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["hook", "gate"])

    # Exit 1, never 2: a missing project is not a "findings exist" block signal,
    # and 2 must stay reserved for that in harnesses where it means "block".
    assert result.exit_code == 1
    output = result.output + result.stderr
    assert "not inside a SMAIRT project" in output
    assert "global harness config" in output


def test_hook_keeps_its_exit_code_promises_when_check_itself_crashes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An internal smairt failure must never break the hook protocol.

    ``report`` promises to always exit 0 and ``gate`` reserves exit 2 for
    "findings exist, block". A crash inside ``run_checks`` is a smairt defect,
    not a finding about the researcher's project -- blocking every edit in the
    session because smairt itself broke would wedge the researcher out of their
    own work with no way to proceed.
    """
    monkeypatch.chdir(_project(tmp_path))

    def _boom(_root: Path) -> None:
        raise RuntimeError("simulated internal failure")

    monkeypatch.setattr("smairt.check.run_checks", _boom)

    report = runner.invoke(app, ["hook", "report"])
    assert report.exit_code == 0, report.output

    gate = runner.invoke(app, ["hook", "gate"])
    assert gate.exit_code == 1, "an internal crash must never be reported as 'findings exist'"
