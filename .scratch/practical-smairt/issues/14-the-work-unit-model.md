# The work-unit model

Type: grilling
Status: resolved

## Question

What are SMAIRT's work units, given that real research (per the post-mortem) is a **spine pipeline** — stages rerun and tweaked until frozen — **plus exploratory probe branches** off it? The current single unit, the iteration (one script, one log, one interpretation), fits neither the spine nor the branching, and the handout's unresolved vocabulary (experiment vs analysis vs run vs route vs branch vs track) all hangs on this.

Decide: the named units, how each maps to files/directories, which get numbered vs named, and how dead ends are separated from keepers. This is the most upstream design decision — the state contract records state *of* these units.

## Answer

**Two work units, no third.**

- **Stage** — one step of the spine pipeline. Ordered, numbered folders: `pipeline/01_align/`, `pipeline/04_de/`. Each holds its script(s), outputs, and a README stating what it does and whether it's frozen.
- **Question** — one exploratory probe hanging off a stage. Dated, named folders: `questions/2026-08-17_replicate3-pca/`. Each holds everything it produced; its README *is* its hypothesis and its interpretation — separate numbered hypothesis files are gone. Grouping subfolders under `questions/` may be earned later; no "track/route" unit exists up front (the tracks table is one of the ledgers that died).

**Machine-readable headers.** Every unit README opens with a few lines of YAML frontmatter — status, one-line claim, date, parent stage. Assistants and `smairt status` reconstruct the whole project picture from headers alone (cheap in tokens, per the researcher's constraint); orientation is always *derived* from headers, never hand-maintained in a ledger.

**Dead ends** stay where they are, marked `status: dead-end` (+ one-line reason) in frontmatter. No mandatory archiving — moving files is manual ledger-keeping in disguise; an occasional tidy-up may be *suggested* by the orientation view but never required.

**Forks.** Researcher's observed pattern: mostly contained, occasionally propagating, with real friction at the transition.
- *Contained fork* (first-class case): sibling variant subfolders inside one stage — `pipeline/04_de/deseq2/`, `pipeline/04_de/limma/`. The stage README records the active variant and why the loser lost; the loser's folder stays as the "what could have been" record.
- *Propagating fork* (supported, not optimized): duplicate the affected spine tail as variant-named stage folders, each variant fully contained in its own folder — visible-as-plain-files over clever (Git branches rejected: invisible to supervision). A dead route's folders get dead-end headers like anything else.
- The contained→propagating *transition* is the concrete first case for the growth-proposal mechanism (see fog): the assistant/CLI proposes the tail duplication, does the folder mechanics, and records why.

**Phases:** resolved separately in [Phase trichotomy](07-phase-trichotomy-principle-or-accident.md) — no phase trees; per-dataset provenance metadata instead.
