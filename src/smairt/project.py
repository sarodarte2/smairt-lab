from __future__ import annotations

from datetime import date
from enum import Enum
from pathlib import Path
from typing import Sequence

import yaml

from smairt import __version__, frontmatter, index
from smairt.fsutil import write_once
from smairt.models import Researcher

SCHEMA_VERSION = 2


class Harness(str, Enum):
    """Assistant harnesses SMAIRT recognizes (Part I, foundation 8: parity, no favorites)."""

    claude_code = "claude-code"
    codex = "codex"
    opencode = "opencode"
    gemini_cli = "gemini-cli"
    cursor = "cursor"
    none = "none"


def find_project_root(start: Path) -> Path | None:
    """Walk upward from ``start`` looking for the nearest ``smairt.yaml``."""
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / "smairt.yaml").is_file():
            return candidate
    return None


def create_project(
    root: Path,
    *,
    name: str,
    researcher: str,
    description: str,
    harness: Harness = Harness.claude_code,
    hpc: bool = False,
    paper: bool = False,
    created: date | None = None,
    scaffold_version: str | None = None,
) -> Path:
    """Render the ten-item day-one scaffold (spec Part II) at ``root``.

    Every file is written once via :func:`smairt.fsutil.write_once`, so re-running
    this against an existing project errors instead of clobbering researcher edits.
    """
    researcher = Researcher(name=researcher).name
    if not description.strip():
        raise ValueError("description must not be empty")

    today = created or date.today()
    version = scaffold_version or __version__

    write_once(
        root / "smairt.yaml",
        _render_identity(name, researcher, description, harness, today, version),
    )

    open_questions = [_PAPER_NOTE] if paper else []
    write_once(root / "STATUS.md", _render_status(today, description, open_questions))
    write_once(root / "AGENTS.md", _AGENTS_PLACEHOLDER)
    write_once(root / "CLAUDE.md", _CLAUDE_BRIDGE)
    write_once(root / ".gitignore", _GITIGNORE)

    write_once(root / "background" / "README.md", _BACKGROUND_README)
    write_once(root / "background" / "question.md", _render_question_md(description))
    write_once(root / "background" / "literature" / ".gitkeep", "")
    write_once(root / "background" / "prior_work" / ".gitkeep", "")

    write_once(root / "data" / "README.md", _DATA_README)
    write_once(root / "scripts" / "README.md", _SCRIPTS_README)
    write_once(root / "experiments" / "README.md", _EXPERIMENTS_README)

    (root / "results").mkdir(parents=True, exist_ok=True)
    index.write_index(root)

    if hpc:
        write_once(root / "hpc" / "README.md", _HPC_README)
        write_once(root / "hpc" / "submit.slurm.example", _HPC_TEMPLATE)

    return root


def _render_identity(
    name: str,
    researcher: str,
    description: str,
    harness: Harness,
    created: date,
    scaffold_version: str,
) -> str:
    config = {
        "schema_version": SCHEMA_VERSION,
        "scaffold_version": scaffold_version,
        "name": name,
        "researcher": researcher,
        "description": description,
        "created": created,
        "harnesses": [] if harness is Harness.none else [harness.value],
        "settings": {"strict_hooks": False},
    }
    return yaml.safe_dump(config, sort_keys=False, default_flow_style=False, allow_unicode=True)


def _render_status(today: date, description: str, open_questions: Sequence[str]) -> str:
    lines = [
        "## Focus",
        description,
        "",
        "## Next",
        "Create the first stage or question with `smairt unit new`.",
        "",
        "## Open questions",
        *[f"- {item}" for item in open_questions],
        "",
        "## Decisions",
        "",
    ]
    return frontmatter.render({"updated": today}) + "\n" + "\n".join(lines) + "\n"


def _render_question_md(description: str) -> str:
    return (
        "# The question\n\n"
        f"{description}\n\n"
        "Replace this with the project's big question: the one everything else here "
        "answers. It should stay stable while the work under `experiments/` moves.\n"
    )


_PAPER_NOTE = "Paper support (a `paper/` overlay) is deferred until real paper work begins."

_AGENTS_PLACEHOLDER = """\
# AGENTS.md

This is a placeholder. The full assistant contract for this project — the two unit
kinds, frontmatter duties, the stakes rule, and the appendable project-learnings
section — ships with a later work package. For now, here is the project's shape:

- `background/` — the question and context this project answers. Never code.
- `data/` — one folder per dataset, each with a provenance README.
- `scripts/` — shared code, called by experiments with parameters.
- `experiments/` — the work: numbered stages and dated questions.
- `results/INDEX.md` — a generated map from every unit to its evidence.

Start by reading `STATUS.md`: focus, next step, open questions. Add work with
`smairt unit new stage` or `smairt unit new question` — never by hand-creating
folders under `experiments/`.
"""

_CLAUDE_BRIDGE = """\
# SMAIRT
@AGENTS.md
"""

_GITIGNORE = """\
# Byte-compiled / cache
__pycache__/
*.py[cod]
.mypy_cache/
.pytest_cache/
.ruff_cache/

# Environments
.venv/
.env

# Editors and OS noise
.DS_Store
.vscode/
.idea/
*.swp

# Large or generated data: uncomment patterns as this project needs them
# *.bam
# *.fastq.gz
# *.h5ad
"""

_BACKGROUND_README = """\
# background/

Context, never code. `question.md` holds the project's big question — stable across
the whole project. `literature/` holds papers and notes; `prior_work/` holds related
prior efforts. Nothing here runs; it orients.
"""

_DATA_README = """\
# data/

One subfolder per dataset. Give each a README with a provenance header: where the
data came from, when, and any transform already applied before it landed here. Raw
and derived data both live here, described — not generated by this folder.
"""

_SCRIPTS_README = """\
# scripts/

Shared, reusable code: anything called by more than one experiment, invoked with
parameters. One-off probe code stays inside the unit that uses it. Prefer extending
a script here over writing a near-duplicate.
"""

_EXPERIMENTS_README = """\
# experiments/

The work, as units. A **stage** (`NN_name/`) is one step of the spine; a
**question** (`YYYY-MM-DD_name/`) is one exploratory probe. Numbered folders sort
above dated ones, so the spine reads top-down. Create units with
`smairt unit new stage` or `smairt unit new question` — never by hand.
"""

_HPC_README = """\
# hpc/

SLURM submission templates for this project. Copy `submit.slurm.example`, edit it
for the job at hand, and keep the copy inside the stage or question it belongs to.
"""

_HPC_TEMPLATE = """\
#!/bin/bash
# Example SLURM submission script. Copy this into the unit it belongs to, rename
# it, and edit the directives below for the job at hand.
#
#SBATCH --job-name=CHANGE_ME
#SBATCH --output=logs/%x-%j.out
#SBATCH --error=logs/%x-%j.err
#SBATCH --time=01:00:00
#SBATCH --mem=8G
#SBATCH --cpus-per-task=4
#SBATCH --partition=CHANGE_ME

# module load / conda activate / source whatever this job needs here.

# srun my_command --with these --args
"""
