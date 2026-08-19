from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from smairt import __version__
from smairt.cli import STUB_COMMANDS, app

runner = CliRunner()


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


def test_each_stub_subcommand_names_itself_and_exits_nonzero() -> None:
    for command in STUB_COMMANDS:
        result = subprocess.run(
            [str(installed_smairt()), command],
            check=False,
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0, command
        assert command in result.stdout, command
        assert "later work package" in result.stdout, command


def test_help_lists_the_full_command_surface() -> None:
    result = subprocess.run(
        [str(installed_smairt()), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    for command in (*STUB_COMMANDS, "new", "unit", "index"):
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
    assert "smairt connect" in result.output


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
