from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

STUB_COMMANDS = ("new", "check", "status", "connect", "unit")


def run(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, check=False, capture_output=True, text=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Install a release artifact and smoke-test its public command."
    )
    parser.add_argument(
        "--artifact", type=Path, required=True, help="Built wheel or source distribution."
    )
    parser.add_argument(
        "--workspace", type=Path, required=True, help="Empty directory for the isolated smoke test."
    )
    arguments = parser.parse_args()
    artifact = arguments.artifact.resolve()
    workspace = arguments.workspace.resolve()
    if not artifact.is_file():
        raise SystemExit(f"Artifact does not exist: {artifact}")
    if workspace.exists() and (not workspace.is_dir() or any(workspace.iterdir())):
        raise SystemExit(f"Workspace must be absent or empty: {workspace}")
    workspace.mkdir(parents=True, exist_ok=True)
    environment = workspace / "environment"
    created = run([sys.executable, "-m", "venv", str(environment)])
    if created.returncode:
        raise SystemExit(created.stderr)
    python = environment / "bin" / "python"
    installed = run([str(python), "-m", "pip", "install", str(artifact)])
    if installed.returncode:
        raise SystemExit(installed.stderr)
    smairt = environment / "bin" / "smairt"
    version = run([str(smairt), "--version"])
    if version.returncode:
        raise SystemExit(version.stderr or version.stdout)
    if not version.stdout.strip().startswith("smairt "):
        raise SystemExit(f"Unexpected --version output: {version.stdout!r}")
    for command in STUB_COMMANDS:
        stub = run([str(smairt), command])
        if stub.returncode == 0:
            raise SystemExit(f"'{command}' was expected to exit nonzero until it ships.")
        if command not in stub.stdout:
            raise SystemExit(f"'{command}' did not name itself in its stub message.")


if __name__ == "__main__":
    main()
