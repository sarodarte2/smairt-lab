# AGENTS.md

Golden Project: A golden fixture project used to catch scaffold drift.

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
was already done to them before they landed in `data/`. Record where a
dataset's bytes physically live with `smairt data new`/`smairt data
locate` — never a new convention of your own.

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
