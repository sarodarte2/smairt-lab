# SMAIRT V2 Design Record

Status: **decided** — produced by the `practical-smairt` wayfinder effort (2026-08-17 → 2026-08-19).
Every decision here traces to a resolved ticket in `.scratch/practical-smairt/issues/`, each carrying its
rationale and evidence. The two research surveys live in `.scratch/practical-smairt/research/`.

**Goal:** a version of SMAIRT the researcher can stress-test on real DE/RNA-seq work the week after
implementation. Success criteria, in the researcher's words: *works, useful, approachable, consistent,
safe to use for science.*

**Implementation strategy:** the five work packages below are subagent-executable. Each carries its own
mini-handout (context, constraints, deliverables, acceptance criteria). WP1→WP2→WP3 have a dependency
spine; WP4 and WP5 can run in parallel after WP3's schemas exist. WP0 (demolition) can run first or
alongside WP1.

---

## Part I — Design foundations

These principles bind every work package. They come from the real-project post-mortem
(ticket 01): the researcher's actual DE project left SMAIRT within days.

1. **Complexity must be supervisable.** The binding constraint is the researcher's comprehension
   budget. A mechanism the researcher cannot understand and verify doesn't just fail — it converts
   their authority into rubber-stamping. Prefer the mechanism a scientist can hold in their head.
2. **Three tiers, strongest first.** (a) *Generated correctly*: conventions are applied by tooling at
   creation time — skeletons, not rules. (b) *Checked mechanically*: `smairt check` verifies what is
   checkable; hooks and CI run it. (c) *Advised*: only the ungeneratable and uncheckable lives as
   prose, and as little of it as possible. Never put weight on tier (c) that tier (a) or (b) could carry.
3. **Derived-first state.** Truth is reconstructed from unit headers + Git. Exactly one file holds
   what cannot be derived: intent (`STATUS.md`). No hand-maintained ledgers, ever — the old scaffold's
   eight ledgers all died (post-mortem; also Pimentel 2019 via the frameworks survey).
4. **A unit is the record of an act of research, not a container of code.** It must hold the question,
   the invocation, the raw evidence, and the interpretation; where the code lives is a pointer.
5. **Human words are sacred.** Tooling writes skeletons once and never regenerates researcher prose.
   `smairt check` validates structure (fields exist, pointers resolve), never wording. The researcher
   editing any file directly is first-class use.
6. **Raw evidence is never edited.** Log files, once written, are immutable — enforced as a check,
   not a folder wall.
7. **Both readers, always.** Every folder is legible to a human (names + README) and to an AI reading
   only frontmatter headers (a few lines per unit — the whole project map for minimal tokens).
8. **Parity across harnesses.** SMAIRT owns the contract; Claude Code, Codex, OpenCode, Gemini CLI,
   Cursor get thin generated wiring. No harness defines a SMAIRT convention. All supported harnesses
   are assumed skill-capable.

---

## Part II — The target workspace

### Day-one scaffold (ten items, identical for every project)

```text
my_project/
├── smairt.yaml       # identity — nothing else
├── STATUS.md         # intent: focus / next / open questions / project-level decisions
├── AGENTS.md         # the 1-page contract + appendable project-learnings section
├── CLAUDE.md         # 2-line bridge: imports @AGENTS.md   (or the selected harness's bridge)
├── .gitignore
├── background/       # question.md, literature/, prior_work/ — context, never code
├── data/             # one subfolder per dataset, each with a provenance-header README
├── scripts/          # shared reusable code, called by experiments with parameters
├── experiments/      # the work: numbered stages + dated questions (single folder)
└── results/
    └── INDEX.md      # GENERATED signpost: every log & figure → the unit that made it
```

No phase trees (synthetic/downloaded/real dies as structure; survives as per-dataset provenance
metadata and as practice guidance — ticket 07). No `hypotheses/`, `analysis/`, `plans/`, `prompts/`,
`docs/` folders — their jobs moved into units, STATUS.md, and the skills (tickets 04, 06, 08).

### The two work units (ticket 14)

**Stage** — one step of the spine. Folder `experiments/NN_name/` (e.g. `03_de/`). Numbered folders
sort above dated ones, so the spine reads top-down. A stage holding alternatives keeps sibling
variant subfolders (`deseq2/`, `limma/`); its README records the active variant and why the loser
lost. A propagating fork duplicates the affected spine tail as variant-named stage folders —
visible as plain files, never hidden in Git branches.

**Question** — one exploratory probe. Folder `experiments/YYYY-MM-DD_name/`. Its README *is* the
hypothesis, the evidence pointers, and the interpretation.

**Every unit contains the standard three subfolders**: `logs/`, `out/`, `figures/` (created with the
unit; empty ones are fine). Dead ends are labeled in place (`status: dead-end` + one-line reason),
never moved. `scripts/` holds code called by more than one experiment; one-off probe code stays in
its unit. Guidance instructs the assistant to prefer extending a shared script (a *notable*-stakes
proposal) over writing a near-duplicate — this is the anti-LLM-rewrite mechanism.

### Unit README schemas (the machine-readable layer)

Stage:

```yaml
---
kind: stage
title: Differential expression
status: active        # active | frozen | dead-end
created: 2026-08-20
variant_active: deseq2   # only when variants exist
decision: ""             # optional: a decision this stage settled
script: run_de.sh        # entry point, or list
log: logs/
---
```

Question:

```yaml
---
kind: question
title: Does excluding replicate 3 change the DE results?
status: open          # open | supported | refuted | inconclusive | dead-end
date: 2026-08-15
hypothesis: Excluding replicate 3 sharpens DE separation
script: probe_de.R    # path, may point at ../../scripts/... ; list allowed
params: "exclude=rep3"   # optional, for shared-script calls
log: logs/probe_de.log
verdict: ""              # one line, filled at close
decision: ""             # optional
---
```

Receipt fields (added when the invoked tool is not this project's code — Case 2 below):

```yaml
tool: nf-core/rnaseq
tool_version: "3.14"
command: "nextflow run nf-core/rnaseq -profile slurm -params-file params.yaml"
repo: ""              # optional: URL + commit for git-hosted workflows
```

Question README body sections (skeleton, written by tooling): `## Why ask this`,
`## What we expected` (before the run), `## What happened` (facts from the log),
`## What it means` (the interpretation — the old analysis/ file, now beside its evidence),
`## Next`.

### The three unit cases (ticket 06)

1. **Own code** — scripts live in the unit (or in `scripts/`, called with `params:`). The normal case.
2. **Outside tool** — the unit is a receipt: config, exact command, raw log, output pointers,
   tool + version pinned in frontmatter. The tool is never copied in.
3. **Pre-existing project** — `smairt adopt` (STRETCH GOAL, see deferrals): lays the contract files
   around existing structure, moves nothing, then proposes thin README-only units referencing
   existing paths, one approval at a time.

### Hypotheses live at two levels

- The project's big question: `background/question.md`. Stable.
- Each probe's hypothesis: in its unit README, written before the run.
- A hypothesis spanning several probes: a bullet in STATUS.md open questions until it earns a
  grouping subfolder under `experiments/` (growth proposal).

### STATUS.md format

```markdown
---
updated: 2026-08-19
---

## Focus
One line: what is being worked on right now.

## Next
One line: the next concrete step.

## Open questions
- A few bullets. Multi-probe hypotheses start here.

## Decisions
- Rare project-level decisions that belong to no single unit.
```

### smairt.yaml (identity only)

```yaml
schema_version: 2
scaffold_version: "<tool version at creation>"
name: My Project
researcher: Name
description: One sentence.
created: 2026-08-20
harnesses: [claude-code]      # harnesses connected via `smairt connect`
settings:
  strict_hooks: false          # opt-in pre-tool blocking (default: warnings only)
```

Removed relative to V0.x: `starting_phase`, `current_phase`, capability state blocks, license
machinery beyond a plain `license:` passthrough. Identity changes rarely; research state never
lives here.

---

## Part III — Work packages

### WP0 — Demolition and retirement

**Context.** Full remake is authorized (ticket 02/13). The old system's weight is itself a failure
cause; carrying it forward would poison the rest.

**Scope.**
- Remove from the generated scaffold: all phase trees, `hypotheses/`, `analysis/` (all ledgers:
  ITERATION_LOG, BREADCRUMB_TRAIL, ANALYSIS_PLAN, RIGOR, REPOSITORY_PLAN, STUDY_REPORT_TEMPLATE,
  templates), `plans/`, `prompts/` (all nine guidance files), `docs/` (12_STEPS, PHILOSOPHY, etc.),
  per-project helper scripts (`new_iteration.py`, `new_track.py`, `record_outcome.py`,
  `select_result.py`, etc.) — their jobs move to `smairt` commands and skills.
- Remove from the tool: the fourteen-screen wizard, framed screens, dashboard, menu/terminal/
  appearance machinery (`terminal.py`, `menu.py`, `appearance.py`, and the interactive bulk of
  `cli.py`). `smairt new` becomes a short sequence of plain prompts.
- Keep untouched: `legacy/cookiecutter/` (historical reference), Git history.
- Preserve as inspiration only (content mined by WP5, files not shipped): AI_CONTEXT's role framing,
  PHILOSOPHY's core insight, KNOWN_PATTERNS' consistency-rules idea.

**Constraints.** Do not delete `.scratch/`, `docs/agents/`, or repo-level (non-scaffold) docs; those
belong to this repo's own development, not to generated projects. Old tests tied to removed
surfaces are removed with them; do not leave skipped-test residue.

**Acceptance.** `uv run pytest` green with the remaining suite; `smairt --help` shows only the new
command surface; no scaffold asset ships that Part II doesn't name.

### WP1 — Scaffold and unit generation (commitments 1 + 2)

**Context.** Tier-1 enforcement: conventions exist because tooling instantiates them.

**Deliverables.**
- The ten-item day-one scaffold rendered by `smairt new` exactly as in Part II, with tool-written
  READMEs in `background/`, `data/`, `scripts/`, `experiments/` explaining their own conventions in
  a few lines each.
- `smairt new` (plain prompts, no TUI): name, researcher, one-line description, harness selection
  (installs wiring via WP4), and 2–3 opt-ins (expect HPC? → `hpc/` folder with SLURM template;
  expect a paper? → note in STATUS open questions; the Paper overlay itself is deferred).
  Complete non-interactive flags for automation.
- `smairt unit new` — creates a stage, question, or receipt skeleton: folder, standard subfolders,
  README with valid frontmatter and body sections, correct numbering/dating. This command is what
  the WP5 skills call; it is the single numbering/dating authority.
- Regeneration of `results/INDEX.md` (invoked by check/status; a standalone `smairt index` is fine).

**Constraints.** Generated Markdown must be short and self-explaining — a colleague proofreading
the repo learns the convention from the folder itself. No file ships that a fresh user wouldn't
read. Skeletons are written once; no regeneration of researcher-edited files, ever.

**Acceptance.** A golden project fixture matches `smairt new` output byte-for-byte (modulo
name/date normalization). `smairt unit new question --title "..."` produces a folder that passes
`smairt check` with zero findings. Total generated prose on day one is under ~150 lines across all
READMEs (vs ~4,400 today).

### WP2 — The state contract: `smairt check` (commitment 3)

**Context.** Tier-2 enforcement. Derived-first: check reads frontmatter + filesystem + Git; it
never maintains its own database.

**Deliverables — check rules (each with a stable ID, JSON output via `--json`):**
1. Frontmatter schema: every unit README parses, `kind`/`status`/dates legal, required fields present.
2. Evidence pointers resolve: `script:`, `log:`, `outputs:`/`paths:` files exist.
3. Receipt completeness: units with `tool:` have non-empty `tool_version` and `command`, and a log.
4. Raw-log immutability: files under any `logs/` unchanged after first commit (Git-based; warn-only
   when Git absent).
5. STATUS drift: `STATUS.md` `updated:` older than the newest change under `experiments/` — report
   which units outran it.
6. Structure drift: files loose in `experiments/` outside any unit; unproposed top-level folders.
7. Closed-question completeness: `status` ∈ {supported, refuted, inconclusive, dead-end} requires a
   non-empty `verdict`.
8. Growth suggestions (advisory, distinct output channel): SLURM/`sbatch` content found → suggest
   `hpc/`; ≥3 questions sharing a name prefix → suggest a grouping folder; paper-words in STATUS →
   suggest the (deferred) Paper overlay.

**Constraints.** Read-only, exit 0/1 (findings), fast enough to run on every session end. Checks
validate structure, never wording (foundation 5).

**Acceptance.** Unit tests per rule (fixture violating exactly that rule); the golden project passes
clean; a deliberately-mangled fixture yields exactly the expected finding IDs.

### WP3 — Orientation: `smairt status` (commitment 4)

**Context.** Ticket 05. The four returning-researcher questions, answered from derived state +
STATUS.md, under one screen.

**Deliverables.** `smairt status` printing: Focus + Next (from STATUS.md); the spine (stages in
order with status/active variant); live questions (open, dated); recently closed (last 2–3, one-line
verdict each); warnings (from WP2). When drift exists, intent is shown but labeled: *"STATUS last
written <date>; these N folders changed since: …"* — never claim falsely, never withhold the
researcher's last words. `--json` for assistants; plain text for humans. Regenerates
`results/INDEX.md` as a side effect.

**Constraints.** No history dump; deep history is the unit trail reached by the links status prints.
Output identical in meaning for human and AI consumers (same command, two formats).

**Acceptance.** On the golden project mid-state fixture, output matches an approved snapshot; with
an induced stale STATUS, the staleness label lists exactly the changed units.

### WP4 — Harness wiring (commitment 5, enforcement half)

**Context.** Tickets 09/10. SMAIRT owns the contract; harnesses get generated wiring.

**Deliverables.**
- `smairt connect <harness>` (also run by `smairt new`'s harness selection): writes the bridge file
  (Claude Code: 2-line `CLAUDE.md` importing `@AGENTS.md`; Gemini: `.gemini/settings.json`
  `context.fileName`; Codex/OpenCode/Cursor: none needed) and the hook config for that harness —
  visible, commented, running only read-only `smairt check`.
- Session-end/stop hook per harness: on findings, feed them back so the assistant proposes fixes —
  including the three-line STATUS.md update — before the session ends. The human approves a diff.
- Optional strictness: when `settings.strict_hooks: true`, also install the pre-tool blocking hook
  (writes outside recognized structure refused). Default off.
- CI template (GitHub Actions) running `smairt check` — the enforcement floor.

**Constraints.** Hook configs are generated files the researcher can read and delete; `connect` is
idempotent; never modify a hook config the researcher has edited (detect and warn instead).

**Acceptance.** On a test project per harness config format: bridge + hook files match approved
fixtures; a seeded drift produces the expected hook feedback text.

### WP5 — AGENTS.md and the skills (commitment 5, guidance half)

**Context.** Tickets 08/12. Tier 3, kept minimal; procedures live in SMAIRT-owned skills shipped
with the tool, never copied into projects.

**Deliverables.**
- The canonical `AGENTS.md` template (~1 page): the two units and the three cases; frontmatter
  duties; evidence rules (raw logs never edited; every claim points at its log); the loop in ten
  lines; **the stakes rule** (label every proposal routine/notable/structural; only structural needs
  explicit yes); **the explanation rule** (notable+: what it does, what it risks scientifically, one
  alternative and why not — in plain language); cheap-data-first as practice; the appendable
  `## Project learnings` section with its prune-as-you-append discipline (replaces
  KNOWN_PATTERNS/CODE_CONVENTIONS for project-specific knowledge).
- Small skills (multiple, per researcher's choice), each thin because `smairt unit new` does the
  mechanics: `smairt-orient` (run status, walk the researcher back in), `smairt-new-question`,
  `smairt-new-stage`, `smairt-close-question` (verdict + What-it-means + STATUS touch),
  `smairt-fork` (contained→propagating mechanics as a structural proposal),
  `smairt-adversarial-review` (argue against the current interpretation from the units' own
  evidence: dead ends, surprises, open questions).
- The old nine guidance files are not shipped (WP0); their surviving ideas live here.

**Constraints.** AGENTS.md must stay ≤ ~120 lines including the learnings section header. Skills
instruct *and invoke* — any skill that would explain a convention should instead call the command
that instantiates it. No skill maintains state.

**Acceptance.** A dry-run transcript exercise: from an empty project, following only AGENTS.md +
skills, an assistant produces a question unit that passes check, closes it, and updates STATUS —
with zero references to files that no longer exist.

### Stretch — `smairt adopt`

Only if the week has room (researcher: "if we have tokens left for it!"). Contract-around,
move-nothing: write the four contract files into an existing repo, then propose README-only
reference units path-by-path, one approval each. Out of scope otherwise; PNNL projects wait for the
shape to survive the stress test.

---

## Part IV — Deferrals (recorded decisions, not omissions)

| Deferred | Until | Ticket |
|---|---|---|
| Full `smairt adopt` + PNNL project migration | after the solo stress test | 06 |
| Distribution & identity (repo naming, version story, PyPI) | the PNNL-sharing gate | 02 |
| Paper overlay (`paper/` workspace, claim→evidence manifest) | growth-proposal once real paper work begins | 06 |
| Study report | spec'd later as a *derived, on-demand* synthesis command — never a maintained file | 04 |
| Windows-native support | unchanged from V0.x (WSL) | — |

## Part V — Validation

The acceptance test for the whole design is the week-after stress test: the researcher's DE/RNA-seq
work restarted fresh in the new shape. Watch for: STATUS drift warnings firing usefully (not
naggingly); whether the spine/question split fits daily reality; whether stakes labels reduce or
merely relabel approval load; any DE-shaped assumption that fails other work shapes. Findings feed
the PNNL-gate revision.
