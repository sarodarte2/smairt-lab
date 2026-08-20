"""``smairt new`` — creates a brand-new project's "day-one scaffold" from scratch.

This is the module a researcher's first command runs through. It renders the
ten starting files/folders a fresh SMAIRT project needs (``smairt.yaml``,
``STATUS.md``, ``AGENTS.md``, ``.gitignore``, ``background/``, ``data/``,
``scripts/``, ``experiments/``, ``results/``, and optionally ``hpc/``) and
writes them once via :func:`smairt.fsutil.write_once` — so running ``smairt
new`` a second time against the same folder is refused rather than silently
overwriting anything.

Most of this file's length is the literal *text* of the generated files
(the big triple-quoted string constants near the bottom, like
``_AGENTS_TEMPLATE`` and ``_GITIGNORE``) — the actual logic is short. Two of
its rendering functions are reused elsewhere because the content must be
byte-identical everywhere it appears: :func:`render_identity` and
:func:`render_status` are also called by :mod:`smairt.adopt` (adopting a
pre-existing project uses the same ``smairt.yaml``/``STATUS.md`` shape, just
with different starting values), and :func:`render_agents_md` is the single
place ``AGENTS.md`` is generated for both ``smairt new`` and ``smairt adopt``.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from pathlib import Path
from typing import Mapping, Sequence

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
    pi = "pi"
    none = "none"


def find_project_root(start: Path) -> Path | None:
    """Walk upward from ``start`` looking for the nearest ``smairt.yaml``.

    This is how every command (``check``, ``status``, ``unit new``, ...)
    figures out "which project am I in" — the same way Git finds the
    repository root by looking for ``.git``. A researcher can run
    ``smairt check`` from any subfolder of their project, not just the top.
    Returns ``None`` if no ``smairt.yaml`` is found before reaching the
    filesystem root (i.e. we're not inside a SMAIRT project at all).
    """
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

    # smairt.yaml is the project's identity file (name, researcher, harness) --
    # written first so every later step happens inside a folder that
    # find_project_root() can already recognize as a SMAIRT project.
    write_once(
        root / "smairt.yaml",
        render_identity(name, researcher, description, harness, today, version),
    )

    # STATUS.md starts with the paper note as its one open question, if the
    # researcher said this project expects to support a paper -- a nudge
    # toward the (currently deferred) Paper overlay, not a real feature yet.
    open_questions = [_PAPER_NOTE] if paper else []
    write_once(root / "STATUS.md", render_status(today, description, open_questions))
    write_once(root / "AGENTS.md", render_agents_md(name, description))
    # CLAUDE.md is the 2-line bridge so Claude Code (which reads CLAUDE.md,
    # not AGENTS.md) still ends up following the same one contract as every
    # other harness -- see CLAUDE_BRIDGE below.
    write_once(root / "CLAUDE.md", CLAUDE_BRIDGE)
    write_once(root / ".gitignore", _GITIGNORE)

    write_once(root / "background" / "README.md", _BACKGROUND_README)
    write_once(root / "background" / "question.md", _render_question_md(description))
    write_once(root / "background" / "literature" / ".gitkeep", "")
    write_once(root / "background" / "prior_work" / ".gitkeep", "")

    write_once(root / "data" / "README.md", _DATA_README)
    write_once(root / "scripts" / "README.md", _SCRIPTS_README)
    write_once(root / "experiments" / "README.md", _EXPERIMENTS_README)

    # results/INDEX.md is derived, not a skeleton (Part I, foundation 3): it's
    # generated fresh here rather than written from a template string, and
    # every later smairt command that touches units regenerates it too.
    (root / "results").mkdir(parents=True, exist_ok=True)
    index.write_index(root)

    if hpc:
        write_once(root / "hpc" / "README.md", _HPC_README)
        write_once(root / "hpc" / "submit.slurm.example", _HPC_TEMPLATE)

    return root


def render_identity(
    name: str,
    researcher: str,
    description: str,
    harness: Harness,
    created: date,
    scaffold_version: str,
    *,
    adoption: Mapping[str, object] | None = None,
) -> str:
    """Render ``smairt.yaml`` (Part II schema). Shared by ``smairt new`` and
    ``smairt adopt`` — the latter passes ``adoption`` (``adopted``/``date``/
    ``known_folders``), the only schema addition adoption makes."""
    config: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "scaffold_version": scaffold_version,
        "name": name,
        "researcher": researcher,
        "description": description,
        "created": created,
        "harnesses": [] if harness is Harness.none else [harness.value],
        "settings": {"strict_hooks": False},
    }
    if adoption is not None:
        config["adoption"] = dict(adoption)
    return yaml.safe_dump(config, sort_keys=False, default_flow_style=False, allow_unicode=True)


_DEFAULT_NEXT_STEP = "Create the first stage or question with `smairt unit new`."


def render_status(
    today: date,
    description: str,
    open_questions: Sequence[str],
    *,
    next_step: str = _DEFAULT_NEXT_STEP,
) -> str:
    """Render ``STATUS.md``. Shared by ``smairt new`` and ``smairt adopt`` — the
    latter passes its own seeded ``next_step`` text."""
    lines = [
        "## Focus",
        description,
        "",
        "## Next",
        next_step,
        "",
        "## Open questions",
        *[f"- {item}" for item in open_questions],
        "",
        "## Decisions",
        "",
    ]
    return frontmatter.render({"updated": today}) + "\n" + "\n".join(lines) + "\n"


def _render_question_md(description: str) -> str:
    """Render ``background/question.md``, seeded with the project's one-line description."""
    return (
        "# The question\n\n"
        f"{description}\n\n"
        "Replace this with the project's big question: the one everything else here "
        "answers. It should stay stable while the work under `experiments/` moves.\n"
    )


_PAPER_NOTE = "Paper support (a `paper/` overlay) is deferred until real paper work begins."


def render_agents_md(name: str, description: str) -> str:
    """The canonical AGENTS.md contract (spec WP5): ~1 page, tier-3 guidance only.

    Everything tier-1 (generated) or tier-2 (checked) can carry is a command
    reference here, not restated as prose — see Part I, foundation 2. Kept
    under the ~120-line cap (including the ``## Project learnings`` header)
    by :mod:`tests.test_project`. Shared verbatim by ``smairt new`` and
    ``smairt adopt`` (one contract, generated the same way everywhere — spec
    Part I foundation 2) — the ONE rendering function, no duplicate template.
    """
    return _AGENTS_TEMPLATE.format(name=name, description=description)


_AGENTS_TEMPLATE = """\
# AGENTS.md

{name}: {description}

## Shape

```
my_project/
├── smairt.yaml       # identity: name, researcher, harnesses
├── STATUS.md         # intent: focus / next / open questions / decisions
├── AGENTS.md         # this file: the contract + project learnings
├── CLAUDE.md         # bridge: imports this file for Claude Code
├── .gitignore
├── background/       # question.md, literature/, prior_work/ — context, never code
├── data/             # one subfolder per dataset, each with provenance
├── scripts/          # shared reusable code, called by experiments with parameters
├── experiments/      # the work: numbered stages + dated questions
└── results/          # results/INDEX.md — GENERATED signpost: evidence -> unit
```

## Units

Two kinds, both under `experiments/`: a **stage** (`NN_name/`, one step of the
spine) and a **question** (`YYYY-MM-DD_name/`, one exploratory probe). Every
unit gets the same three subfolders: `logs/`, `out/`, `figures/`.

Three cases: **own code** (scripts live in the unit or in `scripts/`, called
with `params:` — the normal case); **outside tool** (the unit is a receipt:
config, exact command, raw log, `tool:`/`tool_version:` pinned in
frontmatter — the tool itself is never copied in); **referenced elsewhere**
(a thin, README-only unit pointing at code that already exists outside
`experiments/` — how a pre-existing project gets adopted).

`smairt unit new stage|question` is the ONLY way to create a unit — it is
the sole numbering and dating authority. Never `mkdir` one by hand.

## Frontmatter duties

Every unit README opens with a YAML block. Keep `status` current; a question
closing needs a one-line `verdict` in the same edit. A dead end is a status
change in place (`status: dead-end` + why, in one line) — never move or
delete the folder. Every evidence pointer (`script:`, `log:`, `outputs:`)
must resolve to a real path; `smairt check` verifies this.

## Evidence rules

Raw logs, once written, are never edited again. Every claim under "What it
means" points at the log (or figure) that backs it — no unsourced claims.
Data files carry a short provenance note: where they came from, when, what
was already done to them before they landed in `data/`.

## The loop

question -> hypothesis (written before the run) -> run (log captured) ->
**What happened** (facts, only what the log shows) -> **What it means**
(your interpretation) -> verdict + STATUS.md update -> next question.

## The stakes rule

Label every proposal you make **routine**, **notable**, or **structural**.
Routine flows without asking. Notable gets a heads-up but doesn't block.
Structural — a new top-level folder, reorganizing the spine, deleting
anything, changing a frozen stage — needs the researcher's explicit yes
before you act.

## The explanation rule

Any notable-or-above proposal states, in plain language: (a) what it does,
(b) what it risks scientifically, (c) one alternative and why not chosen.
Never present one option as the only way — the researcher evaluates the
tradeoff, you don't make it for them.

## Practices

Prefer cheap or synthetic data before expensive or real data — a practice,
not a folder. Prefer extending a script in `scripts/` over writing a
near-duplicate (that's a notable proposal). Run `smairt status` when you
join a session; run `smairt check` before you end one. At session end,
propose a 3-line STATUS.md update (focus / next / one open question).

## Project learnings

<!-- Append project-specific patterns and solved errors here as they come
     up; prune as you append. Keep this whole file under ~120 lines. -->
"""

# The 2-line Claude Code bridge (spec Part II): imports AGENTS.md so Claude Code,
# which reads CLAUDE.md and not AGENTS.md natively, still gets the same contract as
# every other harness. Public so smairt.connect can reuse it verbatim (WP4).
CLAUDE_BRIDGE = """\
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
