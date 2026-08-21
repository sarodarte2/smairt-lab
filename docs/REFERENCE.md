# SMAIRT reference

Complete command reference, the harness wiring matrix, `smairt check`'s rule
table and output format, and the development/release gates. For what SMAIRT
is and why, install instructions, and the everyday loop, see
[`README.md`](../README.md).

Every command works from anywhere inside a project (it walks up to find
`smairt.yaml`, the way Git finds `.git`), except `smairt new`, which creates
one.

## Commands

| Command | What it does |
| --- | --- |
| `smairt new [OPTIONS]` | Create a new project: the ten-item day-one scaffold. |
| `smairt adopt [OPTIONS]` | Lay the contract files around a pre-existing directory; moves nothing. |
| `smairt check [--json]` | Audit the state contract (frontmatter, evidence pointers, drift). Exits 1 on any finding. |
| `smairt status [--json]` | Orientation: focus, spine, live/closed questions, warnings, suggestions. |
| `smairt connect <harness>` / `--ci` | Wire (or re-wire) one harness's hooks and skills, or write the CI workflow. |
| `smairt unit new stage\|question --title ...` | Create one unit under `experiments/` — the sole numbering/dating authority. |
| `smairt data new\|locate\|list` | Record and list where each dataset's bytes physically live. |
| `smairt index` | Regenerate `results/INDEX.md`. |
| `smairt hook report\|gate\|brief` | Speaks a harness hook's exit-code protocol; called by generated wiring, not usually typed by hand. |

Flag lists below were verified against `uv run smairt <command> --help` on
this tree.

### `smairt new`

Creates the ten-item day-one scaffold (`smairt.yaml`, `STATUS.md`,
`AGENTS.md`, `.gitignore`, `background/`, `data/`, `scripts/`,
`experiments/`, `results/`, and optionally `hpc/`).

| Flag | Description |
| --- | --- |
| `--name TEXT` | Project name. |
| `--researcher TEXT` | Researcher name. |
| `--description TEXT` | One-line project description. |
| `--question TEXT` | The project's big question: becomes `background/question.md`'s body and `STATUS.md`'s `## Focus`. Optional — omitted entirely (never written as a placeholder) when skipped. |
| `--expertise TEXT` | The researcher's field plus how much of the computing side they want explained. Optional, same skip behavior as `--question`; recorded as `smairt.yaml`'s `expertise:` and added to `AGENTS.md` as a `## Who you're working with` section. |
| `--path PATH` | Parent directory for the new project (default: current directory). The project folder itself is derived from `--name`. |
| `--harness [claude-code\|codex\|opencode\|gemini-cli\|cursor\|pi\|none]` | Assistant harness to record in `smairt.yaml`; wires it up immediately (hooks and skills — see *Connect a coding assistant* below). `none` skips wiring for now; connect one later with `smairt connect <harness>`. |
| `--hpc` / `--no-hpc` | Also generate `hpc/` with a commented SLURM template. |
| `--paper` / `--no-paper` | Leave a note under `STATUS.md`'s open questions that a paper overlay is a deferred, not-yet-built feature. |
| `--git` / `--no-git` | Initialize a Git repository and stage the scaffold (never commits). A `--no-git` choice is recorded as `smairt.yaml`'s `settings.git: false`, which suppresses the `SMAIRT101` advisory. |

`--name`/`--researcher`/`--description`/`--harness` prompt interactively when
omitted at a real terminal. `--question`/`--expertise`/`--hpc`/`--paper`/`--git`
also prompt interactively when omitted; with no terminal attached, `--question`
and `--expertise` are skipped (left absent) and `--hpc`/`--paper`/`--git` take
their documented default instead (no HPC, no paper note, Git initialized) — so
a non-interactive `smairt new` needs only
`--name`/`--researcher`/`--description`/`--harness`. `--question`, `--expertise`,
`--hpc`, and `--paper` are all independent of each other and of everything
else.

Running `smairt new` inside an already-existing SMAIRT project (any
ancestor directory holding its own `smairt.yaml`) still creates the new
project, but prints a warning naming the nesting and which project's
`smairt.yaml` wins for commands run inside the new one — the same voice as
the Git nesting message below. The outer project's own `smairt check` also
flags the nested folder specifically (rule `SMAIRT006`), rather than the
generic "unrecognized folder" message an unrelated folder gets.

### `smairt adopt`

Lays the same contract files (`smairt.yaml`, `STATUS.md`, `AGENTS.md`,
`experiments/README.md`, `results/INDEX.md`) around a pre-existing directory
and moves nothing; every top-level folder that already existed is recorded
in `smairt.yaml`'s `adoption.known_folders` so `smairt check` doesn't warn
about it.

| Flag | Description |
| --- | --- |
| `--name TEXT` | Project name. |
| `--researcher TEXT` | Researcher name. |
| `--description TEXT` | One-line project description. |
| `--expertise TEXT` | The researcher's field plus how much of the computing side they want explained. Optional (same skip behavior as `smairt new --expertise`). |
| `--path PATH` | Directory to adopt (default: current directory). |
| `--harness [claude-code\|codex\|opencode\|gemini-cli\|cursor\|pi\|none]` | Assistant harness to record in `smairt.yaml` (same behavior as `smairt new`). |

`smairt adopt` has no `--question`: it never seeds a big question on a
pre-existing project.

### `smairt check`

| Flag | Description |
| --- | --- |
| `--json` | Emit machine-readable JSON instead of human-readable text. |

See *`smairt check`: rules and output* below for the full rule table and
output format.

### `smairt status`

| Flag | Description |
| --- | --- |
| `--json` | Emit machine-readable JSON instead of human-readable text. |

Reuses `smairt check`'s rules internally; prints focus, spine, live/closed
questions, warnings, and suggestions rather than a raw finding list.

### `smairt connect`

| Argument / Flag | Description |
| --- | --- |
| `harness` | Harness to wire up: `claude-code`, `codex`, `opencode`, `gemini-cli`, `cursor`, `pi`; or `ci` for the GitHub Actions template. |
| `--ci` | Write the GitHub Actions CI template instead of harness wiring. |

Omitting both the `harness` argument and `--ci` fails with the list of valid
choices. If `smairt.yaml`'s `settings.strict_hooks` is `true`, the blocking
(`smairt hook gate`) wiring is also written; otherwise only the reporting
(`smairt hook report`) wiring is.

### `smairt unit new`

| Argument / Flag | Description |
| --- | --- |
| `kind` | `stage` or `question` (required). |
| `--title TEXT` | Unit title (required). |
| `--hypothesis TEXT` | The probe's hypothesis (question units only). |
| `--from TEXT` | Origin unit's folder name (question units only): this question was prompted by that unit's result. Validated to exist at creation. |
| `--receipt` | Record this unit as a receipt for an outside tool. |
| `--tool TEXT` | Outside tool name (with `--receipt`). |
| `--tool-version TEXT` | Outside tool version (with `--receipt`). |
| `--command TEXT` | Exact command that was run (with `--receipt`). |
| `--repo TEXT` | Tool repo URL and commit, if any (with `--receipt`). |
| `--ref TEXT` | Existing path this unit references, relative to the project root (repeatable). Creates a thin, README-only reference unit pointing at code that already exists elsewhere in the tree — how `smairt adopt` gives pre-existing work a unit without moving it. Validated to exist at creation. |

A **stage** folder is `NN_slug/` (e.g. `01_align-reads/`), numbered
automatically and only ever upward; status is one of `active`, `frozen`, or
`dead-end`. A **question** folder is `YYYY-MM-DD_slug/`, dated rather than
numbered; status is one of `open`, `supported`, `refuted`, `inconclusive`,
or `dead-end`. Both get `logs/`, `out/`, and `figures/` subfolders and a
README whose frontmatter `smairt check` validates (`--ref` units are
README-only, with none of those subfolders).

A question unit's `hypothesis:` must hold real text regardless of status
(rule SMAIRT009). Closing a question (any status other than `open`)
requires a non-empty `verdict:` (rule SMAIRT007) and a non-empty `##
Analysis plan` body section (rule SMAIRT010). `--from` records
`prompted_by:` in the new question's frontmatter, naming the unit whose
result raised it; `smairt check` errors (rule SMAIRT008) if that value is
present but does not resolve to a real unit, but never requires the field
itself.

### `smairt data new`

| Argument / Flag | Description |
| --- | --- |
| `name` | Dataset name; slugified into `data/<slug>/` (required). |
| `--hpc HOST:PATH` | An HPC location (repeatable). |
| `--url TEXT` | A download-source URL (repeatable). |
| `--local TEXT` | An additional local path, beyond the dataset folder (repeatable). |
| `--note TEXT` | Note applied to every location passed in this call. |

### `smairt data locate`

| Argument / Flag | Description |
| --- | --- |
| `name` | Dataset name, as passed to `smairt data new` (required). |
| `--hpc HOST:PATH` | An HPC location. |
| `--url TEXT` | A download-source URL. |
| `--local TEXT` | A local path. |
| `--note TEXT` | Optional note for this location. |

Exactly one of `--hpc`/`--url`/`--local` is required per call. Each dataset
location is one of `local` (a path inside the project), `hpc`
(`HOST:PATH`), or `url` (a download source); a dataset can have several,
recorded as per-dataset frontmatter rather than a central registry file.

### `smairt data list`

| Flag | Description |
| --- | --- |
| `--json` | Emit machine-readable JSON instead of human-readable text. |

### `smairt index`

No flags. Regenerates `results/INDEX.md` from every unit's frontmatter
header; a question unit with a resolving `prompted_by:` is nested under its
origin's row (indented) rather than getting its own column.

### `smairt hook`

| Argument | Description |
| --- | --- |
| `mode` | `report` prints findings and always exits 0 (safe for session-end hooks); `brief` prints `smairt status`'s human view and always exits 0 (safe for session-start hooks); `gate` exits 2 while findings exist — the block code Claude Code, Codex, and Cursor hooks understand. |

Called by the generated wiring below, not usually typed by hand.

## Connect a coding assistant

`smairt connect <harness>` wires a harness's native hook and rules surface,
plus a copy of SMAIRT's eight skills, to the one shared contract —
`AGENTS.md` plus `smairt check`:

| Harness | Generated wiring | Skills installed to |
| --- | --- | --- |
| `claude-code` | `CLAUDE.md` bridge + `.claude/settings.json` SessionStart (`smairt hook brief`) and Stop (`smairt hook report`) hooks | `.claude/skills/<name>/SKILL.md` |
| `codex` | `.codex/hooks.json` (loads once you trust the project) | `.agents/skills/<name>/SKILL.md` |
| `cursor` | `.cursor/hooks.json` + always-applied `.cursor/rules/smairt.mdc` | `.agents/skills/<name>/SKILL.md` |
| `opencode` | `.opencode/plugins/smairt-check.ts` | `.agents/skills/<name>/SKILL.md` |
| `pi` | `.pi/extensions/smairt-check.ts` | `.agents/skills/<name>/SKILL.md` |
| `gemini-cli` | smairt keys merged into `.gemini/settings.json`, including a SessionStart hook running `smairt hook brief` | `.agents/skills/<name>/SKILL.md` |

Codex, OpenCode, and pi read `AGENTS.md` natively, so they need no bridge
file. Claude Code is the one harness with no documented `.agents/` support,
so it alone gets the `.claude/skills/` path; the other five share
`.agents/skills/` (Codex's only repo-local skills path, Gemini CLI's
higher-precedence alias, and a documented location for Cursor, OpenCode, and
pi). Skills are copied, not referenced — no harness has a project-local
"also read skills from this path" setting, and a reference would resolve to
a per-venv path that breaks on clone — so a `smairt` upgrade requires
deleting the installed copy and re-running `connect` to refresh it; each
installed `SKILL.md` carries a comment saying so. See
[`AI_SKILL_USAGE.md`](AI_SKILL_USAGE.md) for what each skill does.

Of the eight skills, only `smairt-adversarial-review` is researcher-invoked
only; on Claude Code, Cursor, and pi that is enforced via a
`disable-model-invocation` frontmatter field, not just stated in the
skill's own text.

Every generated file names itself as generated, runs only read-only smairt
commands (`smairt hook report`/`smairt hook gate`, never anything that
writes), and can be deleted to disable the wiring; re-running `connect`
never overwrites a file you have edited — it reports it as "unchanged" if
identical, or warns and leaves it alone if it differs. `.gemini/settings.json`
is the one exception: it is merged key-by-key rather than compared whole,
since researchers are likely to already have a populated file for unrelated
reasons, so only missing keys are ever added.

The hooks call `smairt hook report`, which surfaces `smairt check` findings
at session end and always exits 0. On Claude Code and Gemini CLI, a
SessionStart hook also calls `smairt hook brief`, which prints `smairt
status`'s human view and always exits 0, so a fresh session orients itself
without the researcher having to think to ask. Setting `settings.strict_hooks:
true` in `smairt.yaml` (then re-running `connect`) also wires `smairt hook
gate`, which exits 2 — the block code these harnesses understand — so edits
are refused while findings exist. `smairt connect --ci` writes a GitHub
Actions workflow, the enforcement floor that binds every contributor
regardless of local hooks.

## `smairt check`: rules and output

`smairt check` runs thirteen finding rules and five advisory suggestion rules
against a project's units, frontmatter, and state. Each rule carries one
stable id that is never renumbered once shipped; the rule, not each way of
violating it, is the unit of identity.

### Findings (severity error/warning; any instance makes the exit code non-zero)

| Rule | Severity | Meaning |
| --- | --- | --- |
| `SMAIRT001` | error | Frontmatter schema invalid: block missing/malformed, kind not recognized, status illegal for that kind, or a required field absent. |
| `SMAIRT002` | error | An evidence pointer (`script:`/`log:`/`outputs:`/`paths:`) does not resolve, or a CLOSED unit's `script:`/`log:` is empty. |
| `SMAIRT003` | error | Receipt completeness: a unit with `tool:` set has an empty `tool_version:`, empty `command:`, or a `log:` that does not exist. |
| `SMAIRT004` | error | Raw-log immutability: a file under a unit's `logs/` was modified in a later commit than the one that added it. |
| `SMAIRT005` | warning | STATUS drift: `STATUS.md`'s `updated:` is older than a unit that has changed since. |
| `SMAIRT006` | warning | Structure drift: a file loose directly under `experiments/` (outside any unit folder), or an unrecognized top-level project folder. |
| `SMAIRT007` | error | Closed-question completeness: status in `{supported, refuted, inconclusive, dead-end}` with an empty `verdict:`. |
| `SMAIRT008` | error | A question's `prompted_by:` is set but does not resolve to a real unit (a folder with its own `README.md`) under `experiments/`. |
| `SMAIRT009` | error | A question unit's `hypothesis:` is present but empty (reference units are exempt). |
| `SMAIRT010` | error | A CLOSED question unit's `## Analysis plan` body section is missing or empty (reference units are exempt). |
| `SMAIRT011` | error | The project's own `smairt.yaml` parses but is empty, isn't a mapping, or is missing/blank on a required identity field (`name:`/`researcher:`/`description:`). |
| `SMAIRT012` | warning | A folder directly under `experiments/` has no `README.md`, so it is invisible to `check`/`status`/`index`. |
| `SMAIRT013` | error | A question's `prompted_by:` chain loops back on itself (a cycle, only reachable by hand-editing frontmatter). |

An unparseable `smairt.yaml` (a genuine YAML syntax error, not just a missing
field) never reaches rule `SMAIRT011` at all — every command, `check`
included, fails fast the moment it resolves the project root, naming the
file, the line where YAML reports the problem, and printing a correct
`smairt.yaml` to repair it by eye. See *Judgment calls* in `check.py`'s
module docstring for the full policy.

### Advisory suggestions (a separate channel; never affect the exit code)

| Rule | Meaning |
| --- | --- |
| `SMAIRT101` | Git is unavailable, so raw-log immutability (`SMAIRT004`) could not be checked at all — one note, not per-file. |
| `SMAIRT102` | SLURM/sbatch content found in a unit but the project has no `hpc/` folder yet. |
| `SMAIRT103` | Three or more question units share a leading slug word: a grouping subfolder may be earned. |
| `SMAIRT104` | `STATUS.md` mentions paper/manuscript/figure-legend work: a pointer to the (deferred) Paper overlay. |
| `SMAIRT105` | A `data/<x>/` subfolder exists with no README, or a README with no `locations:` entry recorded — one note, not per-dataset. |

Reference units (created with `smairt unit new ... --ref`) are exempt from
`SMAIRT009` and `SMAIRT010` — they describe work adopted after the fact,
never framed as a testable claim, so a retroactive hypothesis or analysis
plan would be meaningless.

### Output format

`smairt check` groups findings as errors or warnings and prints a count of
each, plus the separate advisory-only suggestions channel:

```text
No errors or warnings.

0 error(s), 0 warning(s), 0 suggestion(s).
```

When there are findings, each is printed as `<RULE> <path>: <message>`,
grouped under an `Errors:` and/or `Warnings:` heading, followed by the same
count line. `smairt check --json` emits the equivalent as machine-readable
JSON. `smairt check` exits 1 if any finding (error or warning) exists, 0
otherwise; `smairt hook gate`/`smairt hook report` translate that into the
exit-code language a harness hook expects (see `smairt hook` above).

## Limits

- `smairt check` diagnoses structure and configuration; it does not inspect
  scientific correctness or modify researcher-authored content.
- The Paper overlay named by `smairt new --paper` is not yet built; today the
  flag only leaves a `STATUS.md` note.
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
