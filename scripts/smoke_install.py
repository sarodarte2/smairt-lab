from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

STUB_COMMANDS: tuple[str, ...] = ()


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
    # Skills are shipped as package data (src/smairt/assets/skills/), not
    # loose files next to the repo checkout, so the only real test that they
    # made it into the artifact is asking the *installed* package for them —
    # this venv has never seen the source tree, only what pip just installed.
    skills_check = run(
        [
            str(python),
            "-c",
            "from smairt.skills import list_skills, read_skill\n"
            "names = list_skills()\n"
            "assert len(names) == 8, f'expected 8 skills, found {names}'\n"
            "for name in names:\n"
            "    assert read_skill(name).startswith('---'), name\n"
            "print(len(names))\n",
        ]
    )
    if skills_check.returncode:
        raise SystemExit(skills_check.stderr or skills_check.stdout)
    if skills_check.stdout.strip() != "8":
        raise SystemExit(f"Expected 8 installed skills, saw: {skills_check.stdout!r}")
    for command in STUB_COMMANDS:
        stub = run([str(smairt), command])
        if stub.returncode == 0:
            raise SystemExit(f"'{command}' was expected to exit nonzero until it ships.")
        if command not in stub.stdout:
            raise SystemExit(f"'{command}' did not name itself in its stub message.")


if __name__ == "__main__":
    main()
