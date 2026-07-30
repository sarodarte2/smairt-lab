"""Offline project, dependency, and release-readiness diagnostics."""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import cast

from smairt import __version__
from smairt.credentials import keyring_health
from smairt.harnesses import list_harnesses
from smairt.locking import read_lock
from smairt.migrations import detect_scaffold, migration_plan
from smairt.models import EnvironmentMode, SmairtConfig
from smairt.project import validate_project
from smairt.safety import release_check
from smairt.transactions import transaction_status
from smairt.updates import project_update_plan

RUNTIME_IMPORTS = {
    "pydantic": "pydantic",
    "pyyaml": "yaml",
    "rich": "rich",
    "prompt-toolkit": "prompt_toolkit",
    "typer": "typer",
    "pypdf": "pypdf",
    "python-docx": "docx",
    "keyring": "keyring",
    "pyzotero": "pyzotero",
    "mcp": "mcp",
}


def doctor(root: Path) -> dict[str, object]:
    """Return a comprehensive local health report without contacting remotes."""
    validation = validate_project(root).as_dict()
    config = SmairtConfig.load(root / "smairt.yaml")
    missing_dependencies = [
        name for name, module in RUNTIME_IMPORTS.items() if importlib.util.find_spec(module) is None
    ]
    git_available = shutil.which("git") is not None
    git_repository = (root / ".git").exists()
    git_required = config.git.enabled
    git_ok = not git_required
    if git_repository and git_available:
        git_ok = (
            subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=root,
                capture_output=True,
                check=False,
            ).returncode
            == 0
        )
    environment_ok = not (
        config.environment.mode is not EnvironmentMode.NONE and shutil.which("conda") is None
    )
    transactions = transaction_status(root)
    harnesses = list_harnesses(root)
    active_harness = next(item for item in harnesses if item["active"])
    harness_ok = not any(
        active_harness.get(key)
        for key in ("missing", "modified", "non_executable", "schema_errors", "manifest_error")
    ) and bool(active_harness.get("adapter_supported"))
    schema = detect_scaffold(root)
    release = release_check(root)
    warnings = []
    if schema in {"v2", "v3", "v4", "v5", "v6", "v7"}:
        warnings.append(
            "Project updates are available; run `smairt update --apply` when ready "
            "(or use Health & updates → Project updates in `smairt menu`)."
        )
    ok = bool(
        validation["ok"]
        and schema in {"v2", "v3", "v4", "v5", "v6", "v7", "v8"}
        and not missing_dependencies
        and (not git_required or git_ok)
        and environment_ok
        and transactions["ok"]
        and harness_ok
    )
    updates = project_update_plan(root)
    blocking_findings = cast(list[dict[str, str]], validation.get("findings", []))
    blocking_findings = [item for item in blocking_findings if item.get("severity") == "error"]
    health_state = (
        "blocked" if not ok else "action_recommended" if updates["updates_available"] else "healthy"
    )
    return {
        "ok": ok,
        "health_state": health_state,
        "blocking_findings": blocking_findings,
        "recommended_updates": updates,
        "warnings": warnings,
        "package": {"version": __version__, "missing_dependencies": missing_dependencies},
        "scaffold": schema,
        "schema_compatible": schema in {"v2", "v3", "v4", "v5", "v6", "v7", "v8"},
        "schema_current": schema == "v8",
        "git": {
            "available": git_available,
            "repository": git_repository,
            "healthy": git_ok,
        },
        "lock": read_lock(root),
        "transactions": transactions,
        "validation": validation,
        "harnesses": harnesses,
        "environment": {
            "configured": config.environment.model_dump(mode="json", exclude_none=True),
            "healthy": environment_ok,
        },
        "migration": migration_plan(root),
        "release": release,
        "sharing_readiness": release,
        "release_ready": bool(ok and release["ok"]),
        "network_accessed": False,
    }


def _command_version(command: list[str]) -> str | None:
    """Return the first version line for an available local executable."""
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    output = (result.stdout or result.stderr).strip()
    return output.splitlines()[0] if output else None


def setup_doctor(*, check_github: bool = False) -> dict[str, object]:
    """Diagnose the user-wide tool setup, contacting GitHub only when requested."""
    git_path = shutil.which("git")
    uv_path = shutil.which("uv")
    conda_path = shutil.which("conda")
    gh_path = shutil.which("gh")
    git_name = None
    git_email = None
    if git_path:
        git_name = _command_version([git_path, "config", "--global", "user.name"])
        git_email = _command_version([git_path, "config", "--global", "user.email"])
    github_authenticated: bool | None = None
    github_message: str | None = None
    if check_github and gh_path:
        try:
            result = subprocess.run(
                [gh_path, "auth", "status"], capture_output=True, text=True, timeout=15, check=False
            )
            github_authenticated = result.returncode == 0
            github_message = (result.stdout or result.stderr).strip()
        except (OSError, subprocess.TimeoutExpired):
            github_authenticated = False
            github_message = "GitHub authentication check failed or timed out"
    supported_python = (3, 11) <= sys.version_info[:2] <= (3, 13)
    shell_files = [
        Path.home() / name
        for name in (".zshrc", ".zprofile", ".bashrc", ".bash_profile", ".profile")
    ]
    conda_initialized = False
    uv_shell_configured = False
    for shell_file in shell_files:
        try:
            content = shell_file.read_text(encoding="utf-8", errors="replace")
            conda_initialized = conda_initialized or "# >>> conda initialize >>>" in content
            uv_shell_configured = uv_shell_configured or any(
                marker in content for marker in (".local/bin", "UV_INSTALL_DIR", "uv tool dir")
            )
        except OSError:
            continue
    env_conda = [os.environ.get(name) for name in ("CONDA_EXE", "MAMBA_EXE")]
    common_conda = next(
        (
            str(candidate)
            for candidate in [
                *(Path(value) for value in env_conda if value),
                Path.home() / "miniforge3/bin/conda",
                Path.home() / "mambaforge/bin/conda",
                Path.home() / "miniconda3/bin/conda",
                Path.home() / "anaconda3/bin/conda",
                Path("/opt/miniforge3/bin/conda"),
                Path("/opt/miniconda3/bin/conda"),
                Path("/opt/anaconda3/bin/conda"),
                Path("/opt/homebrew/Caskroom/miniforge/base/bin/conda"),
            ]
            if candidate.is_file()
        ),
        None,
    )
    uv_install_dir = os.environ.get("UV_INSTALL_DIR")
    xdg_bin = os.environ.get("XDG_BIN_HOME")
    common_uv = next(
        (
            str(candidate)
            for candidate in [
                *(Path(value) / "uv" for value in (uv_install_dir, xdg_bin) if value),
                Path.home() / ".local/bin/uv",
                Path.home() / ".cargo/bin/uv",
            ]
            if candidate.is_file()
        ),
        None,
    )
    return {
        "ok": bool(supported_python and git_path and uv_path),
        "python": {"version": sys.version.split()[0], "supported": supported_python},
        "smairt": {"version": __version__},
        "git": {
            "available": bool(git_path),
            "path": git_path,
            "version": _command_version([git_path, "--version"]) if git_path else None,
            "user_name": git_name,
            "user_email": git_email,
        },
        "uv": {
            "available": bool(uv_path),
            "path": uv_path,
            "version": _command_version([uv_path, "--version"]) if uv_path else None,
            "shell_path_configured": uv_shell_configured,
            "installation_found_outside_path": common_uv if not uv_path else None,
            "recovery": (
                "Add the discovered uv directory to PATH, run 'uv tool update-shell', "
                "then reopen the terminal."
                if common_uv and not uv_path
                else None
            ),
        },
        "conda": {
            "available": bool(conda_path),
            "path": conda_path,
            "version": _command_version([conda_path, "--version"]) if conda_path else None,
            "required_for_smairt": False,
            "recommended_for_project_environments": True,
            "shell_initialized": conda_initialized,
            "installation_found_outside_path": common_conda if not conda_path else None,
            "recovery": (
                "Run the discovered conda executable with 'init', then reopen the terminal."
                if common_conda and not conda_path
                else None
            ),
        },
        "github_cli": {
            "available": bool(gh_path),
            "path": gh_path,
            "authenticated": github_authenticated,
            "message": github_message,
        },
        "credential_backend": keyring_health(),
        "network_accessed": check_github,
    }
