# SMAIRT: Scientific Method with AI Research Toolkit

SMAIRT creates readable, hypothesis-driven scientific research workspaces for
coding assistants, then keeps checking that the workspace stays disciplined as
the work grows. The installed `smairt` command is the supported project
creation path. It supports macOS, Linux, and Windows through WSL; native
Windows support is deferred. This is a preview-stage tool (pre-1.0): the
command surface is small and stable within a release, but still growing.

## Install The Preview

This repository provides a local/repository preview, not a PyPI release. On
macOS, Linux, or WSL with Python 3.11 through 3.13, clone the repository and
install the current checkout as an isolated tool:

```bash
git clone https://github.com/sarodarte2/smairt-lab.git
cd smairt-lab
uv tool install .
smairt --version
```

`pipx` is the fallback when `uv` is unavailable:

```bash
pipx install .
smairt --version
```

Use `uv tool install --force .` or `pipx reinstall smairt` after updating your
checkout. Native Windows is not supported; use WSL instead.

## Create A Project

Run `smairt new` with no flags for a short set of prompts (project name,
researcher, one-line description, a numbered choice of harness, then y/n
questions for HPC support, paper support, and Git):

```bash
smairt new
```

Or pass everything up front, for scripts and automation:

```bash
smairt new \
  --name "Signal Recovery" \
  --researcher "A. Researcher" \
  --description "Does denoising recover the true signal in low-SNR imaging data?" \
  --harness claude-code \
  --no-hpc \
  --no-paper \
  --git
```

`--path` sets the parent directory (default: the current directory); the
project folder itself is derived from `--name`. `--harness` records one
coding assistant in `smairt.yaml` and wires it up immediately (see *Connect A
Coding Assistant* below) — pass `--harness none` to skip wiring for now and
connect one later. `--hpc` additionally generates `hpc/` with a commented
SLURM template; `--paper` only leaves a note under STATUS.md's open
questions that a paper overlay is a deferred, not-yet-built feature — neither
flag is required, and each is independent of the other.

With no terminal attached, an omitted `--hpc/--paper/--git` question takes its
documented default (no HPC, no paper note, Git initialized) instead of
prompting, so a non-interactive `smairt new` needs only
`--name`/`--researcher`/`--description`/`--harness`.

A pre-existing directory (an old analysis folder, a lab's existing repo) is
adopted instead of created fresh:

```bash
smairt adopt --name "Legacy Imaging" --researcher "A. Researcher" \
  --description "Pre-existing imaging pipeline, brought under SMAIRT." \
  --harness none
```

`smairt adopt` lays the same contract files (`smairt.yaml`, `STATUS.md`,
`AGENTS.md`, `experiments/README.md`, `results/INDEX.md`) around whatever is
already there and moves nothing; every top-level folder that already existed
is recorded in `smairt.yaml` so `smairt check` doesn't warn about it.

## Generated Workspace

`smairt new` writes ordinary, readable files — this is the actual tree from a
project created with the command above:

```text
signal_recovery/
├── smairt.yaml         # identity: name, researcher, harnesses, settings
├── STATUS.md           # focus / next / open questions / decisions
├── AGENTS.md           # the contract: shape, units, evidence rules
├── CLAUDE.md           # 2-line bridge so Claude Code reads AGENTS.md
├── .gitignore
├── background/
│   ├── README.md
│   ├── question.md     # the project's one big, stable question
│   ├── literature/
│   └── prior_work/
├── data/
│   └── README.md       # one subfolder per dataset added later
├── scripts/
│   └── README.md       # shared, reusable code
├── experiments/
│   └── README.md       # the work, as units (see below)
├── results/
│   └── INDEX.md        # GENERATED — regenerate with `smairt index`
└── .claude/settings.json   # written because --harness claude-code
```

`AGENTS.md` is the one contract every coding assistant is pointed at — read
by Codex, OpenCode, and pi natively, and by Claude Code through the `CLAUDE.md`
bridge (always generated, regardless of which harness you chose). It documents
the shape above, the two kinds of unit, the evidence and stakes rules, and
ends with a `## Project learnings` section an assistant appends to over time.

The work itself lives under `experiments/` as **units**, and `smairt unit
new` is the only supported way to create one — never `mkdir` by hand, because
this command is also what assigns the number or date:

```bash
smairt unit new stage --title "Align reads"
smairt unit new question --title "Why is signal low" \
  --hypothesis "Detector gain misconfigured"
```

A **stage** (`experiments/01_align-reads/`) is one step of the project's
planned spine, numbered and only ever going up. A **question**
(`experiments/2026-08-19_why-is-signal-low/`) is one dated, exploratory
probe. Both get `logs/`, `out/`, and `figures/` subfolders and a README whose
frontmatter `smairt check` validates. `--receipt --tool ... --tool-version
... --command ...` records a unit as a receipt for an outside tool's run
instead of your own code; `--ref path/to/existing` (repeatable) creates a
thin, README-only unit pointing at code that already exists elsewhere in the
tree — how `smairt adopt` gives pre-existing work a unit without moving it.

`results/INDEX.md` is the one file above that is derived, not a skeleton:
`smairt index` (and `smairt status`, and unit creation) regenerate it from
every unit's frontmatter, so it is never hand-edited.

## Collaborating In Git

`--git/--no-git` (default: asks at a terminal, initializes when there is
none to ask) runs `git init` and stages the generated scaffold — `git add
-A`, nothing more. SMAIRT never commits; that first commit is a deliberate
act left to you. If the new project sits inside a Git repository that starts
above it — a lab monorepo, a researcher's whole project tree already one
repo — SMAIRT leaves Git alone rather than nesting a second repository
inside the first; the scaffold shows up as untracked files in the outer repo
for you to add when you're ready. If `git` isn't installed, project creation
still succeeds and the command says so.

The point of tracking `smairt.yaml`, `AGENTS.md`, the harness wiring under
`.claude/`/`.codex/`/etc., and the CI workflow under `.github/workflows/` is
that every collaborator who clones the project — human or coding assistant —
gets the same contract and the same enforcement, not a private convention
that lives only in one person's head or one session's context.

## Where Data Lives

Research data is usually too big for Git, or lives on a cluster's scratch
disk a laptop can't reach. `data/<slug>/` holds a README per dataset; the
data files themselves are git-ignored by default (see the generated
`.gitignore`), so a collaborator who clones the project gets every README
but none of the bytes.

```bash
smairt data new imaging_raw \
  --hpc cluster.example.edu:/scratch/proj/raw --note "raw acquisition, untouched"
smairt data locate imaging_raw --url https://example.org/dataset.zip
smairt data list
```

```text
imaging_raw (data/imaging_raw)
  local data/imaging_raw/
  hpc   cluster.example.edu:/scratch/proj/raw  # raw acquisition, untouched
  url   https://example.org/dataset.zip
```

Each location is one of `local` (a path inside the project), `hpc`
(`HOST:PATH`), or `url` (a download source); a dataset can have several. This
is per-dataset frontmatter, not a central registry file — truth lives next
to the dataset it describes, in the same folder a researcher is already
looking in when they wonder where something is. `smairt check` nudges
(advisory only, never blocking) toward recording a location for any
`data/<x>/` folder that doesn't have one yet.

## Connect A Coding Assistant

`smairt connect <harness>` wires a harness's native hook and rules surface to
the one shared contract — `AGENTS.md` plus `smairt check` — so every assistant
gets the same discipline through its own best channel:

| Harness | Generated wiring |
| --- | --- |
| `claude-code` | `CLAUDE.md` bridge + `.claude/settings.json` Stop hook |
| `codex` | `.codex/hooks.json` (loads once you trust the project) |
| `cursor` | `.cursor/hooks.json` + always-applied `.cursor/rules/smairt.mdc` |
| `opencode` | `.opencode/plugins/smairt-check.ts` |
| `pi` | `.pi/extensions/smairt-check.ts` |
| `gemini-cli` | smairt keys merged into `.gemini/settings.json` |

Codex, OpenCode, and pi read `AGENTS.md` natively, so they need no bridge
file. Every generated file names itself as generated, runs only read-only
smairt commands, and can be deleted to disable the wiring; re-running
`connect` never overwrites a file you have edited (it reports it as
"unchanged" if identical, or warns and leaves it alone if it differs).

The hooks call `smairt hook report`, which surfaces `smairt check` findings at
session end and always exits 0. Setting `settings.strict_hooks: true` in
`smairt.yaml` (then re-running `connect`) also wires `smairt hook gate`, which
exits 2 — the block code these harnesses understand — so edits are refused
while findings exist. `smairt connect --ci` writes a GitHub Actions workflow,
the enforcement floor that binds every contributor regardless of local hooks.

## Command Reference

Every command works from anywhere inside a project (it walks up to find
`smairt.yaml`, the way Git finds `.git`), except `smairt new`, which creates
one.

| Command | What it does |
| --- | --- |
| `smairt new [OPTIONS]` | Create a new project: the day-one scaffold. |
| `smairt adopt [OPTIONS]` | Lay the contract files around a pre-existing directory; moves nothing. |
| `smairt check [--json]` | Audit the state contract (frontmatter, evidence pointers, drift). Exits 1 on any finding. |
| `smairt status [--json]` | Orientation: focus, spine, live/closed questions, warnings, suggestions. |
| `smairt connect <harness>` / `--ci` | Wire (or re-wire) one harness's hooks, or write the CI workflow. |
| `smairt unit new stage\|question --title ...` | Create one unit under `experiments/` — the sole numbering/dating authority. |
| `smairt data new\|locate\|list` | Record and list where each dataset's bytes physically live. |
| `smairt index` | Regenerate `results/INDEX.md`. |
| `smairt hook report\|gate` | Speaks a harness hook's exit-code protocol; called by generated wiring, not usually typed by hand. |

`smairt check` groups findings as errors or warnings and prints a count of
each, plus a separate advisory-only suggestions channel that never affects
the exit code:

```text
No errors or warnings.

0 error(s), 0 warning(s), 0 suggestion(s).
```

## Limits

- Project Check diagnoses structure and configuration; it does not inspect
  scientific correctness or modify researcher-authored content.
- The Paper overlay named by `smairt new --paper` is not yet built; today the
  flag only leaves a STATUS.md note.
- HPC support supplies guidance and a template, not scheduler integration.
  SMAIRT does not submit or manage cluster jobs.
- Native Windows support is deferred; use WSL.

## Development

Clone into an ordinary local directory rather than a cloud-synced folder such
as OneDrive, iCloud Drive, or Dropbox. Generated development files (`.venv`,
caches, `dist`, and smoke-install workspaces) are large, disposable, and not
tracked by Git; syncing them wastes upload capacity and can corrupt a virtual
environment when files are offloaded to the cloud:

```bash
git clone https://github.com/sarodarte2/smairt-lab.git ~/Developer/smairt-lab
cd ~/Developer/smairt-lab
```

Install development dependencies and run all release gates locally:

```bash
uv sync --all-extras --locked
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest tests/test_cli.py
uv run pytest
uv build
uv run python scripts/smoke_install.py --artifact dist/smairt-0.4.0-py3-none-any.whl --workspace .smoke/wheel
uv run python scripts/smoke_install.py --artifact dist/smairt-0.4.0.tar.gz --workspace .smoke/sdist
```

GitHub Actions runs these gates on Ubuntu and macOS with Python 3.11, 3.12, and
3.13.
