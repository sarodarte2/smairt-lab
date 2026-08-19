from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from smairt import __version__
from smairt.cli import STUB_COMMANDS


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


def test_help_lists_exactly_the_stub_command_surface() -> None:
    result = subprocess.run(
        [str(installed_smairt()), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    for command in STUB_COMMANDS:
        assert command in result.stdout
    for retired in ("open", "repair", "settings", "inspect", "regenerate", "paper", "hpc"):
        assert retired not in result.stdout
