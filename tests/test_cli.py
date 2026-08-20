"""Tests for the ``smairt`` command line itself (src/smairt/cli.py).

Uses Typer's ``CliRunner`` to invoke commands in-process (fast) and, for a
couple of tests that need the real installed console script, ``subprocess``
against the actual ``smairt`` executable. Checks flag parsing, error
messages, and exit codes -- not the generated file content itself (that's
covered by each command's own module's tests, e.g. test_project.py).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from smairt import __version__
from smairt.cli import STUB_COMMANDS, app
from smairt.project import Harness, create_project

runner = CliRunner()

GIT_AVAILABLE = shutil.which("git") is not None


def installed_smairt() -> Path:
    return Path(sys.executable).with_name("smairt")


def test_version_flag_reports_the_installed_version() -> None:
    result = subprocess.run(
        [str(installed_smairt()), "--version"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == f"smairt {__version__}"


def test_no_stub_commands_remain() -> None:
    # WP4 shipped the last stub (`connect`); this tuple should stay empty.
    assert STUB_COMMANDS == ()


def test_help_lists_the_full_command_surface() -> None:
    result = subprocess.run(
        [str(installed_smairt()), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    for command in ("new", "adopt", "unit", "status", "index", "check", "connect"):
        assert command in result.stdout
    for retired in ("open", "repair", "settings", "inspect", "regenerate", "paper", "hpc"):
        assert retired not in result.stdout


def test_new_non_interactive_with_complete_flags_prompts_for_nothing(
    tmp_path: Path,
) -> None:
    result = runner.invoke(
        app,
        [
            "new",
            "--name",
            "CLI Project",
            "--researcher",
            "Ada Lovelace",
            "--description",
            "Exercises smairt new end to end.",
            "--path",
            str(tmp_path),
            "--harness",
            "claude-code",
            "--no-hpc",
            "--no-paper",
        ],
        input="",  # No stdin available: a stray prompt would hang, not just misbehave.
    )

    assert result.exit_code == 0, result.output
    root = tmp_path / "cli_project"
    assert (root / "smairt.yaml").is_file()
    config = yaml.safe_load((root / "smairt.yaml").read_text())
    assert config["name"] == "CLI Project"
    # `smairt new` wires the selected harness's hooks via the same logic as
    # `smairt connect` (WP4), rather than deferring to a later work package.
    assert (root / ".claude" / "settings.json").is_file()
    assert ".claude/settings.json" in result.output


@pytest.mark.skipif(not GIT_AVAILABLE, reason="git is not installed")
def test_new_git_flag_initializes_a_repo_and_stages_but_does_not_commit(
    tmp_path: Path,
) -> None:
    result = runner.invoke(
        app,
        [
            "new",
            "--name",
            "Git Project",
            "--researcher",
            "Ada Lovelace",
            "--description",
            "Exercises --git end to end.",
            "--path",
            str(tmp_path),
            "--harness",
            "none",
            "--no-hpc",
            "--no-paper",
            "--git",
        ],
        input="",
    )

    assert result.exit_code == 0, result.output
    root = tmp_path / "git_project"
    assert (root / ".git").is_dir()
    assert "staged the scaffold" in result.output
    staged = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain"], capture_output=True, text=True
    ).stdout
    assert "A  smairt.yaml" in staged
    log = subprocess.run(["git", "-C", str(root), "log"], capture_output=True, text=True)
    assert log.returncode != 0  # nothing committed


@pytest.mark.skipif(not GIT_AVAILABLE, reason="git is not installed")
def test_new_git_flag_inside_an_existing_repo_skips_instead_of_nesting(
    tmp_path: Path,
) -> None:
    # `tmp_path` itself is already a Git work tree (a lab monorepo, or a
    # researcher's whole project tree being one repo) before `smairt new`
    # creates the project folder underneath it -- `smairt new --git` must
    # not silently nest a second repo inside the first.
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True)

    result = runner.invoke(
        app,
        [
            "new",
            "--name",
            "Nested Project",
            "--researcher",
            "Ada Lovelace",
            "--description",
            "Exercises --git inside an existing repo.",
            "--path",
            str(tmp_path),
            "--harness",
            "none",
            "--no-hpc",
            "--no-paper",
            "--git",
        ],
        input="",
    )

    assert result.exit_code == 0, result.output
    assert "existing Git repository" in result.output
    root = tmp_path / "nested_project"
    assert not (root / ".git").exists()


def test_new_inside_an_existing_smairt_project_warns_but_still_creates(
    tmp_path: Path,
) -> None:
    """DG-3: `smairt new` run inside an existing SMAIRT project must warn
    (naming the situation, and which project wins for commands run inside
    the new one) but still create the project -- matching the voice of the
    Git nesting message right above (`init_git`'s "this project sits inside
    an existing Git repository...")."""
    outer = tmp_path / "outer"
    create_project(
        outer,
        name="Outer",
        researcher="Ada Lovelace",
        description="The outer project.",
        harness=Harness.none,
        created=date(2026, 1, 1),
        scaffold_version="0.0.0-test",
    )

    result = runner.invoke(
        app,
        [
            "new",
            "--name",
            "Inner Project",
            "--researcher",
            "Ada Lovelace",
            "--description",
            "Nested inside the outer project.",
            "--path",
            str(outer),
            "--harness",
            "none",
            "--no-hpc",
            "--no-paper",
            "--no-git",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "sits inside an existing SMAIRT project" in result.output
    inner = outer / "inner_project"
    assert (inner / "smairt.yaml").is_file()


def test_new_outside_any_project_prints_no_nesting_warning(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "new",
            "--name",
            "Standalone Project",
            "--researcher",
            "Ada Lovelace",
            "--description",
            "Not nested inside anything.",
            "--path",
            str(tmp_path),
            "--harness",
            "none",
            "--no-hpc",
            "--no-paper",
            "--no-git",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "sits inside an existing SMAIRT project" not in result.output


def test_new_no_git_flag_leaves_no_git_directory(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "new",
            "--name",
            "No Git Project",
            "--researcher",
            "Ada Lovelace",
            "--description",
            "Exercises --no-git end to end.",
            "--path",
            str(tmp_path),
            "--harness",
            "none",
            "--no-hpc",
            "--no-paper",
            "--no-git",
        ],
        input="",
    )

    assert result.exit_code == 0, result.output
    root = tmp_path / "no_git_project"
    assert not (root / ".git").exists()


@pytest.mark.skipif(not GIT_AVAILABLE, reason="git is not installed")
def test_new_without_a_git_flag_defaults_to_git_in_a_non_interactive_session(
    tmp_path: Path,
) -> None:
    # No --git/--no-git at all, and CliRunner never presents a real tty (even
    # with input=""), so the "only ask at a real terminal" gate in cli.py's
    # `new` should fall through to the confirm's own default (True) instead
    # of blocking on stdin that will never arrive.
    result = runner.invoke(
        app,
        [
            "new",
            "--name",
            "Default Git Project",
            "--researcher",
            "Ada Lovelace",
            "--description",
            "Exercises the unset --git default end to end.",
            "--path",
            str(tmp_path),
            "--harness",
            "none",
            "--no-hpc",
            "--no-paper",
        ],
        input="",
    )

    assert result.exit_code == 0, result.output
    root = tmp_path / "default_git_project"
    assert (root / ".git").is_dir()


def test_new_non_interactive_with_only_identity_flags_defaults_hpc_and_paper_off(
    tmp_path: Path,
) -> None:
    # No --hpc/--no-hpc, --paper/--no-paper, or --git/--no-git at all. CliRunner
    # never presents a real tty (even with input=""), so the "only ask at a
    # real terminal" gate in cli.py's `new` should fall through to each
    # confirm's own default (False for hpc/paper) instead of blocking on
    # stdin that will never arrive -- this is the exact repro for the bug
    # where an assistant harness or CI calling `smairt new` with just
    # name/researcher/description/harness used to abort.
    result = runner.invoke(
        app,
        [
            "new",
            "--name",
            "Headless Project",
            "--researcher",
            "Ada Lovelace",
            "--description",
            "Exercises the unset HPC/paper-support defaults end to end.",
            "--path",
            str(tmp_path),
            "--harness",
            "none",
        ],
        input="",
    )

    assert result.exit_code == 0, result.output
    root = tmp_path / "headless_project"
    assert not (root / "hpc").exists()
    status = (root / "STATUS.md").read_text(encoding="utf-8")
    assert "paper support" not in status.lower()


def test_new_explicit_hpc_flag_still_creates_hpc_folder(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "new",
            "--name",
            "Hpc Project",
            "--researcher",
            "Ada Lovelace",
            "--description",
            "Exercises an explicit --hpc flag end to end.",
            "--path",
            str(tmp_path),
            "--harness",
            "none",
            "--hpc",
            "--no-paper",
        ],
        input="",
    )

    assert result.exit_code == 0, result.output
    root = tmp_path / "hpc_project"
    assert (root / "hpc").is_dir()


def test_new_refuses_to_overwrite_an_existing_project(tmp_path: Path) -> None:
    flags = [
        "new",
        "--name",
        "CLI Project",
        "--researcher",
        "Ada Lovelace",
        "--description",
        "First run.",
        "--path",
        str(tmp_path),
        "--harness",
        "none",
        "--no-hpc",
        "--no-paper",
    ]
    first = runner.invoke(app, flags, input="")
    assert first.exit_code == 0, first.output

    second = runner.invoke(app, flags, input="")

    assert second.exit_code != 0
    assert "refusing to overwrite" in second.output


def test_new_warns_when_name_slugifies_to_nothing(tmp_path: Path) -> None:
    """Regression: a project name made entirely of emoji/symbols used to fall
    back to the generic folder name 'project' with no warning printed on
    first use -- see M-1 in the friction inventory. The fallback must be
    announced so a second, differently-named run's "refusing to overwrite"
    collision isn't a total surprise."""
    result = runner.invoke(
        app,
        [
            "new",
            "--name",
            "🎉🎉🎉",
            "--researcher",
            "Ada Lovelace",
            "--description",
            "Symbols only.",
            "--path",
            str(tmp_path),
            "--harness",
            "none",
            "--no-hpc",
            "--no-paper",
            "--no-git",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "no letters or digits" in result.output
    assert (tmp_path / "project").is_dir()


def test_new_surfaces_a_write_error_cleanly_when_path_is_not_a_directory(
    tmp_path: Path,
) -> None:
    """Regression: `--path` naming a plain file used to crash `smairt new` with
    a raw `NotADirectoryError` traceback instead of a one-line error naming
    the path and the problem."""
    blocking_file = tmp_path / "a_plain_file.txt"
    blocking_file.write_text("not a directory\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "new",
            "--name",
            "Blocked",
            "--researcher",
            "Ada Lovelace",
            "--description",
            "Blocked by a file.",
            "--path",
            str(blocking_file),
            "--harness",
            "none",
            "--no-hpc",
            "--no-paper",
            "--no-git",
        ],
    )

    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert str(blocking_file) in result.output


def test_new_prompts_only_for_missing_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        app,
        ["new", "--name", "Prompted Project", "--path", str(tmp_path)],
        input="Ada Lovelace\nA project created via prompts.\nclaude-code\nn\nn\n",
    )

    assert result.exit_code == 0, result.output
    assert (tmp_path / "prompted_project" / "smairt.yaml").is_file()


def test_new_reprompts_with_a_friendly_message_on_an_invalid_harness_answer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        app,
        ["new", "--name", "Prompted Project", "--path", str(tmp_path)],
        input="Ada Lovelace\nA project created via prompts.\nnotaharness\nclaude-code\nn\nn\n",
    )

    assert result.exit_code == 0, result.output
    assert "isn't one of the choices above" in result.output
    assert (tmp_path / "prompted_project" / "smairt.yaml").is_file()


def test_adopt_prompts_only_for_missing_fields(tmp_path: Path) -> None:
    root = tmp_path / "existing_project"
    root.mkdir()
    (root / "README.md").write_text("# Existing project\n\nPre-SMAIRT notes.\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["adopt", "--name", "Adopted Project", "--path", str(root)],
        input="Ada Lovelace\nA project adopted via prompts.\nclaude-code\n",
    )

    assert result.exit_code == 0, result.output
    assert (root / "smairt.yaml").is_file()


def _check_project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    create_project(
        root,
        name="CLI Check Project",
        researcher="Ada Lovelace",
        description="Exercises the smairt check command surface.",
        harness=Harness.none,
        created=date.today(),
        scaffold_version="0.0.0-test",
    )
    return root


def test_cli_check_exits_zero_on_a_clean_fresh_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _check_project(tmp_path)
    monkeypatch.chdir(root)

    result = runner.invoke(app, ["check"])

    assert result.exit_code == 0, result.output


def test_cli_check_refuses_outside_a_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["check"])

    assert result.exit_code != 0
    assert "not a SMAIRT project" in result.output


def test_cli_check_fails_fast_on_unparseable_smairt_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DG-1's fail-fast half: a genuine YAML syntax error in smairt.yaml must
    stop `check` with a clean, repair-focused message -- never a traceback,
    never a silently "clean" project."""
    root = _check_project(tmp_path)
    (root / "smairt.yaml").write_text("name: X\n  researcher: bad indent\n", encoding="utf-8")
    monkeypatch.chdir(root)

    result = runner.invoke(app, ["check"])

    assert result.exit_code == 1, result.output
    assert "not valid YAML" in result.output
    assert "line 2" in result.output
    assert "A correct smairt.yaml looks like this" in result.output
    assert "Traceback" not in result.output


def test_cli_status_fails_fast_on_unparseable_smairt_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _check_project(tmp_path)
    (root / "smairt.yaml").write_text("name: X\n  researcher: bad indent\n", encoding="utf-8")
    monkeypatch.chdir(root)

    result = runner.invoke(app, ["status"])

    assert result.exit_code != 0
    assert "not valid YAML" in result.output


def test_cli_hook_fails_fast_on_unparseable_smairt_yaml_and_never_exits_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Exit 1, never 2 -- exit 2 must stay reserved for "findings exist,
    # block the action" in every harness hook protocol this tool speaks.
    root = _check_project(tmp_path)
    (root / "smairt.yaml").write_text("name: X\n  researcher: bad indent\n", encoding="utf-8")
    monkeypatch.chdir(root)

    result = runner.invoke(app, ["hook", "gate"])

    assert result.exit_code == 1, result.output
    assert "not valid YAML" in result.output


def test_cli_check_json_output_parses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _check_project(tmp_path)
    monkeypatch.chdir(root)

    result = runner.invoke(app, ["check", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["findings"] == []
    assert "summary" in payload


def test_cli_status_runs_on_a_fresh_project_and_regenerates_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _check_project(tmp_path)
    index_path = root / "results" / "INDEX.md"
    before = index_path.read_text(encoding="utf-8")
    monkeypatch.chdir(root)

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0, result.output
    for heading in (
        "Focus:",
        "Next:",
        "Spine:",
        "Live questions:",
        "Recently closed:",
        "Warnings:",
    ):
        assert heading in result.output
    assert index_path.read_text(encoding="utf-8") == before  # unchanged content, still regenerated


def test_cli_status_json_output_parses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _check_project(tmp_path)
    monkeypatch.chdir(root)

    result = runner.invoke(app, ["status", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["spine"] == []
    assert "summary" in payload


def test_cli_status_refuses_outside_a_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["status"])

    assert result.exit_code != 0
    assert "not a SMAIRT project" in result.output


def test_cli_check_reports_status_drift_after_a_unit_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from smairt.units import create_stage

    root = _check_project(tmp_path)
    create_stage(root, "Alignment", created=date.today())
    # Force STATUS.md to look older than the unit that was just created.
    status_path = root / "STATUS.md"
    status_path.write_text(
        status_path.read_text(encoding="utf-8").replace(str(date.today()), "2020-01-01"),
        encoding="utf-8",
    )
    monkeypatch.chdir(root)

    result = runner.invoke(app, ["check"])

    assert result.exit_code != 0
    assert "SMAIRT005" in result.output
    assert "01_alignment" in result.output
