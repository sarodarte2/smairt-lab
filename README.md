# SMAIRT: Scientific Method with AI Research Toolkit

SMAIRT scaffolds a readable, hypothesis-driven research project — folders,
README frontmatter, a small contract file — and then keeps checking that the
project stays disciplined as the work grows: every claim points at the log or
figure that backs it, every question states its hypothesis before the run,
and nothing gets renumbered or overwritten by hand. It never touches your
actual analysis code or data; it manages the *structure* around it, so both
you and any coding assistant working alongside you are reading from the same
contract instead of a private convention that lives only in one session's
context.

The installed `smairt` command is the supported project-creation path. It
runs on macOS, Linux, and Windows through WSL (native Windows support is
deferred — see [REFERENCE.md](docs/REFERENCE.md#limits)). This is a
preview-stage tool (pre-1.0): the command surface is small and stable within
a release, but still growing.

There is no worked example or tutorial in this repository — see *Where to go
next* below for why, and what to read instead.

## Install

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

After updating your checkout, reinstall with `uv tool install --force .` or
`pipx reinstall smairt`.

## Create a project

Run `smairt new` with no flags for a short set of prompts — project name,
researcher, one-line description, a numbered choice of coding assistant
("harness"), then yes/no questions for HPC support, paper support, and Git:

```bash
smairt new
```

Or pass everything up front, for scripts and automation:

```bash
smairt new \
  --name "Signal Recovery" \
  --researcher "A. Researcher" \
  --description "Does denoising recover the true signal in low-SNR imaging data?" \
  --question "Does denoising recover the true signal in low-SNR live-cell imaging, or does it invent structure?" \
  --expertise "computational imaging; comfortable in Python, new to version control" \
  --harness claude-code \
  --no-hpc \
  --no-paper \
  --git
```

`--question` and `--expertise` are both optional — omit either and it's simply
absent from `smairt.yaml`, not filled with a placeholder. `--question` becomes
`background/question.md`'s body and `STATUS.md`'s `## Focus`; `--expertise` is
recorded in `smairt.yaml` and added to `AGENTS.md` as a `## Who you're working
with` section, so an assistant calibrates jargon to it from the first session.

`--harness` records one coding assistant in `smairt.yaml` and immediately
wires it up — its hooks, and SMAIRT's own skills — so it starts working
inside the contract from the first session rather than needing to be taught
it in conversation. Every flag `smairt new` accepts, including `--hpc` and
`--paper`, is documented in full in
[REFERENCE.md](docs/REFERENCE.md#smairt-new).

A pre-existing directory — an old analysis folder, a lab's existing repo —
is adopted instead of created fresh. `smairt adopt` lays the same contract
files around whatever is already there and moves nothing:

```bash
smairt adopt --name "Legacy Imaging" --researcher "A. Researcher" \
  --description "Pre-existing imaging pipeline, brought under SMAIRT." \
  --harness none
```

Running `smairt new` from inside a directory that is already a SMAIRT
project (any parent folder holding its own `smairt.yaml`) still creates the
new project, but warns that it is nesting one project inside another and
names which project's `smairt.yaml` wins for commands run inside the new
one — the outer project only ever sees the nested folder as unfamiliar
structure otherwise.

## The shape you get

`smairt new` writes ordinary, readable files — this is the actual tree from
a project created with the command above:

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
│   └── INDEX.md         # GENERATED — regenerate with `smairt index`
├── .claude/settings.json      # written because --harness claude-code
└── .claude/skills/             # SMAIRT's skills, copied in for this harness
```

`AGENTS.md` is the one contract every coding assistant is pointed at — read
by Codex, OpenCode, and pi natively, and by Claude Code through the
`CLAUDE.md` bridge. It documents the shape above, the two kinds of unit, and
the evidence rules, and ends with a `## Project learnings` section an
assistant appends to over time.

## The loop you work in

The work itself lives under `experiments/` as **units**, and `smairt unit
new` is the only supported way to create one — never `mkdir` by hand,
because this command is also what assigns the number or date:

```bash
smairt unit new stage --title "Align reads"
smairt unit new question --title "Why is signal low" \
  --hypothesis "Detector gain misconfigured"
```

A **stage** is one step of the project's planned spine, numbered and only
ever going up. A **question** is one dated, exploratory probe. A question's
`hypothesis:` must hold real text, and its `## Analysis plan` section — what
you'll measure and how you'll judge the outcome — must be filled in before
the question can close. Neither is a flag you are forced to pass up front:
you can create the unit and write both in your editor a minute later. What
you cannot do is leave them empty. Both rules exist for the
same reason: stating the claim and the test *before* you see the result is
what keeps a look at the data from turning into a claim invented afterward
to fit it (a well-known failure mode in research, sometimes called HARKing).
`smairt check` enforces both.

If a question exists because something in another unit's result raised it —
a batch effect noticed in a figure, an odd value in a log — link it with
`--from <origin-unit>` rather than burying it as a note inside the unit that
raised it. The rule of thumb: once you can state the new claim in one line,
it has earned its own unit.

Two more shapes worth knowing: `--receipt --tool ... --tool-version ...
--command ...` records a unit as a receipt for an outside tool's run instead
of your own code; `--ref path/to/existing` (repeatable) creates a thin,
README-only unit pointing at code that already exists elsewhere in the tree
— how `smairt adopt` gives pre-existing work a unit without moving it.
`--ref`, like `--from`, is validated to exist at creation.

Two commands orient you at any point:

```bash
smairt status   # focus, spine, live/closed questions, warnings
smairt check    # audits frontmatter, evidence, and drift; exits 1 on any finding
```

`results/INDEX.md` is the one file in the tree that is derived, not a
skeleton: `smairt index` regenerates it from every unit's frontmatter, so it
is never hand-edited. A question linked with `--from` shows up nested under
the unit that raised it, so that lineage stays visible without turning the
index into a graph.

The full flag list for every command above, plus `smairt check`'s complete
rule table and output format, is in
[REFERENCE.md](docs/REFERENCE.md).

## Connect a coding assistant

`smairt connect <harness>` wires a harness's native hook and rules surface,
plus SMAIRT's own skills, to the one shared contract — `AGENTS.md` plus
`smairt check` — so every assistant gets the same discipline and the same
procedures through its own best channel. It supports Claude Code, Codex,
Cursor, OpenCode, Gemini CLI, and pi; the full wiring matrix is in
[REFERENCE.md](docs/REFERENCE.md#connect-a-coding-assistant).

Every generated file names itself as generated, runs only read-only `smairt`
commands, and can be deleted to disable the wiring; re-running `connect`
never overwrites a file you have edited. Setting `settings.strict_hooks:
true` in `smairt.yaml` (then re-running `connect`) makes those hooks refuse
edits while findings exist, rather than only reporting them.
`smairt connect --ci` writes a GitHub Actions workflow — the enforcement
floor that binds every contributor regardless of local hooks.

## Collaborating in Git

`--git/--no-git` on `smairt new` (default: asks at a terminal, initializes
when there is none to ask) runs `git init` and stages the generated
scaffold — nothing more. SMAIRT never commits; that first commit is a
deliberate act left to you. If the new project sits inside a Git repository
that starts above it, SMAIRT leaves Git alone rather than nesting a second
repository inside the first. A `--no-git` choice is recorded as
`settings.git: false` in `smairt.yaml`, so `smairt check` recognizes the
opt-out as deliberate and doesn't keep suggesting Git (advisory `SMAIRT101`)
on every run.

Tracking `smairt.yaml`, `AGENTS.md`, the harness wiring, and the CI workflow
means every collaborator who clones the project — human or coding assistant
— gets the same contract and the same enforcement, not a private convention
that lives only in one person's head or one session's context.

## Where data lives

Research data is usually too big for Git, or lives on a cluster's scratch
disk a laptop can't reach. `data/<slug>/` holds a README per dataset; the
data files themselves are git-ignored by default, so a collaborator who
clones the project gets every README but none of the bytes.

```bash
smairt data new imaging_raw \
  --hpc cluster.example.edu:/scratch/proj/raw --note "raw acquisition, untouched"
smairt data locate imaging_raw --url https://example.org/dataset.zip
smairt data list
```

Each location is one of `local`, `hpc` (`HOST:PATH`), or `url`; a dataset
can have several. This is per-dataset frontmatter, not a central registry
file — truth lives next to the dataset it describes, in the same folder a
researcher is already looking in when they wonder where something is.

## Where to go next

- [`docs/REFERENCE.md`](docs/REFERENCE.md) — every command's full flag list,
  the harness wiring matrix, `smairt check`'s rule table and output format,
  and the development and release gates.
- Your project's own generated `AGENTS.md` — the contract your assistant
  actually reads.
- [`docs/AI_SKILL_USAGE.md`](docs/AI_SKILL_USAGE.md) — what each of SMAIRT's
  skills does and how `smairt connect` delivers them.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — a tour of this
  repository's own code, for anyone extending SMAIRT itself.

A worked end-to-end example is a deliberate, acknowledged gap, not an
oversight — the previous tutorials and demos drifted out of sync with the
tool they described until neither was trustworthy, so they were removed
rather than patched. A CI-tested replacement is planned as separate future
work.
