# Approachable SMAIRT — wayfinder map

Label: wayfinder:map

## Destination

The repository, **changed in place**, so that a terminal-capable scientist who
reads Python but may not write it can install SMAIRT, understand what it is and
why it exists, and run a hypothesis-driven project through it without hitting a
stale document, a broken path, or a scientific convention SMAIRT has no way to
record — with the assistant reliably carrying SMAIRT's own procedures into every
session.

Reached when: no document in the repo describes a tool that no longer exists;
the two named scientific gaps (sidequest lineage, pre-specified analysis plan)
are decided and implemented; `smairt connect` delivers the skills; and the
friction walk's findings are fixed with regression tests behind them.

## Notes

- **Execution is carried into this map** — this overrides wayfinder's plan-don't-do
  default. But decision tickets resolve *before* the execution tickets that depend
  on them; no execution ticket runs on an undecided convention.
- **Audience floor (charting round):** a terminal-capable scientist who can paste
  and run commands and can *read* Python, but may not write it. "Amateur readable"
  is measured against that reader. The assistant-only path (a scientist who has
  never opened a terminal) is the acknowledged *direction*, not this map's scope —
  it is blocked on an install story this map cannot reach.
- **Feature scope (charting round):** friction removal, plus features that close a
  gap the audience floor exposes. A feature earns its place by unblocking that
  reader, not by being a good idea. Pure ideation goes to Not yet specified.
- **Complexity must be earned _and_ supervisable** — carried forward from
  [practical-smairt](../practical-smairt/map.md). Every proposed mechanism answers
  "what observed problem requires this?" and "can the researcher supervise it?"
- **Do not re-decide `practical-smairt`.** That map is REACHED and its spec is what
  the `v2-rebuild` branch implements. Its decisions are settled input here.
- Skills each session should consult: `/grilling` + `/domain-modeling` for HITL
  tickets. Per domain-modeling, a ticket that resolves a new domain term writes it
  into `CONTEXT.md` inline, as it resolves — not batched.
- Standing preference: at most 3 questions per round, multiple-choice preferred.
  The user is a practicing scientist who co-developed SMAIRT — challenge their
  assumptions, don't defer, don't replace their judgment.
- Working branch: `v2-rebuild`.

### Charting-round decisions

- **Doc surface (Q4):** delete the stale set outright — `QUICKSTART.md`, all three
  `TUTORIAL*.md`, and all 8 `demos/`. The README becomes the single path in. A
  worked example returns as a separate effort (see Out of scope).
- **Skills delivery (Q5):** `smairt connect` installs the skills, alongside the
  hooks it already writes — same command, same per-harness dispatch, same
  never-overwrite-your-edits policy. Accepted as the harder but correct option.
- **README shape (Q7):** split into a short approachable `README.md` and a
  `docs/REFERENCE.md` holding the command tables and harness matrix. Register stays
  **professional** — approachable, not casual.
- **Code readability (Q9):** the Python is already well-documented; goal #2's code
  half is satisfied by deleting dead weight, not by adding prose.
- **Friction method (Q8):** hands-on adversarial walk first, then regression tests
  encoding what the walk actually found — not tests written from imagination.

### Established facts (charting round)

Verified against the `v2-rebuild` working tree:

- `CONTEXT.md` is **entirely v1 vocabulary** (screens, semantic palette, capability,
  phase trichotomy, scaffold blueprint, action token). Zero occurrences of *stage,
  question, spine, receipt, verdict, harness, dataset* — the words the tool now runs on.
- `QUICKSTART.md` and all three tutorials say "V0.1", clone `PNNL-CompBio/smairt-template`
  (not the actual remote), describe the deleted wizard, and pass flags that no longer
  exist (`--slug`, `--domain`, `--phase`, `--assistant`, `--accept-license`).
- All 8 `demos/` are v1-shaped: `analysis/`, `data/synthetic|downloaded|real`,
  `experiments/01_synthetic`. None shows the shape `smairt new` now generates.
- Nothing installs `skills/smairt-*` anywhere. `docs/AI_SKILL_USAGE.md` says only
  "make `skills/` available to an assistant."
- `src/smairt/scaffold.py` and `src/smairt/assets/scaffold-blueprint.yaml` are
  reachable only from `tests/test_scaffold.py` and `scripts/scaffold_diff.py`.
- ~~`skills/` is packaged by nothing.~~ **Fixed** by
  [ticket 11](issues/11-ship-the-skills-in-the-package.md). Root cause was the
  location, not the packaging config: hatchling ships everything tracked under
  `src/smairt` already.
- `README.md` (12.6KB) and `src/smairt/*.py` (4,410 lines) are accurate and v2-current.

## Decisions so far

<!-- one line per closed ticket: gist + link -->

- [Where each harness loads skills from](issues/03-harness-skills-delivery.md) — all six harnesses have a project-local skills surface; `.agents/skills/<name>/SKILL.md` reaches five, Claude Code alone needs `.claude/skills/`, so the dispatch is two paths, not six. **Copy, not reference** — reference is not expressible in four of six, and would resolve to a per-venv path that breaks on clone. Blocking prerequisite found: `skills/` ships in neither the wheel nor the sdist, so an installed `smairt` cannot reach it — split out as [ticket 11](issues/11-ship-the-skills-in-the-package.md). **Verified a second time against primary sources via Context7:** Codex's `.agents/skills/` discovery is confirmed at source level (`core-skills/src/loader.rs`), no feature flag, trust does not appear to gate it — so the tracker-issue doubt is largely retired and its smoke-test downgrades to a sanity check; Claude Code's docs enumerate skill locations without `.agents/`, confirming the two-path design; OpenCode is natively supported with per-skill permission globs. New finding: Claude Code's `disable-model-invocation` and Codex's `agents/openai.yaml` can *enforce* the researcher-invoked-only rule that `smairt-adversarial-review` currently only asserts in prose.

- [Ship the skills inside the package](issues/11-ship-the-skills-in-the-package.md) — the eight skills now live at `src/smairt/assets/skills/`, resolved through `src/smairt/skills.py` via `importlib.resources`; verified present in both wheel and sdist and readable from an installed venv, with the assertion wired into `smoke_install.py` and therefore into CI. Ticket premise partly wrong: `pyproject.toml` needed no change (hatchling already ships tracked files under `src/smairt`), and `README.md` never referenced the old path — the `git mv` alone was the fix.

- [Deliver the skills through `smairt connect`](issues/09-deliver-skills-through-connect.md) — one `_install_skills()` helper on the existing dispatch, two paths (`.claude/skills/` for Claude Code, `.agents/skills/` for the other five), copied not referenced, with a provenance notice that never names a harness so the shared root stays byte-identical and idempotent. ADR 0004 records it. **Codex's documented policy file was found to remove the skill entirely rather than only stop auto-invocation (reproduced independently against codex-cli 0.146.0) and is deliberately not written** — `smairt-adversarial-review` is explicit-invocation-only, so that file would delete the mechanism, not enforce it. Enforcement is real on Claude Code, Cursor, and pi; prose elsewhere.

- [The sidequest and unit lineage](issues/01-sidequest-lineage.md) — a sidequest is an ordinary question unit carrying `prompted_by:` (child→parent, set by `--from` at creation), not a new unit kind. The boundary is the **hypothesis test**: a finding stays inside until you can state a new testable claim in one line — chosen over "needs its own run", which is silent exactly where HARKing lives (a new claim formed from data already in hand). `AGENTS.md` states a verdict answers its own `hypothesis:` and nothing else; `smairt check` errors on a *dangling* `prompted_by:` but never requires the field. `results/INDEX.md` nests prompted questions under their origin; `smairt status` deliberately does not. Glossary gains a relationship, not a noun.

- [The pre-specified analysis plan](issues/02-pre-specified-analysis-plan.md) — a required `## Analysis plan` body section (not a frontmatter line: a real plan doesn't fit on one, and forcing it yields `plan: standard analysis`, which looks like compliance), non-empty to **close**. **Ticket premise was wrong and is corrected: hypothesis-before-run is NOT enforced today** — an empty `hypothesis:` passes `check` clean, verified empirically — so an empty hypothesis becomes an error too. Amendments keep the original and append a greppable `**Amended <date>:**` line rather than being punished. `smairt-new-question` asks at creation so before-the-run is the normal path; the close check is a backstop. Question units only. **Timing is deliberately not recorded** — a disclosure field was proposed and dropped: any two-valued label where one value is better is a grade, and the amendment marker already does the honest version.

- [Implement the scientific conventions](issues/10-implement-the-scientific-conventions.md) — `SMAIRT008/009/010`, `--from`, `## Analysis plan` in the question template, `INDEX.md` lineage nesting, contract and skill text, ADR 0005. Two review corrections: `INDEX.md` indented with `&nbsp;` entities that read as literal junk in a plain-text view (now a real U+00A0), and `AGENTS.md` never mentioned `--from` at all — invisible to any assistant that reads the contract but not the one skill, since `check` deliberately never nags for the link.

- [Retire the stale and vestigial surface](issues/04-retire-the-stale-surface.md) — 735 files gone: QUICKSTART, three tutorials, eight demos, `legacy/`, `plans/`, `MODERNIZATION_PROPOSAL`, and the scaffold-blueprint vestige (precondition verified: nothing under `src/smairt/` imports it). `adversarial_review1.md` moved, not deleted, since a resolved map cites it. Review additions: `skills.py`'s docstring cited the deleted blueprint, and **ADRs 0001–0003 were still marked `Accepted` while describing machinery the rebuild deleted** — now marked Superseded, content kept verbatim.

- [Rewrite CONTEXT.md](issues/05-rewrite-context-md.md) — 25 v2 terms sourced from the code; zero occurrences of screen/palette/blueprint/capability/phase remain. Core Relationships and Invariants dropped rather than re-derived (spec-shaped assertions, not definitions — and a second source of truth that would drift from `ARCHITECTURE.md`). Review fixes: `Rule` claimed there were ten, ignoring the advisory `SMAIRT101`–`SMAIRT105`; `Evidence pointer` inverted the open/closed strictness and omitted that `paths:` resolves from the project root.

- [Split the README](issues/06-split-the-readme.md) — `README.md` (237 lines) is the path in; `docs/REFERENCE.md` (319) holds the flag tables, harness matrix, and full rule table. Professional register, explains *why* each convention exists, states plainly that there is no worked example. Review catches: the README claimed a hypothesis was required **at creation** (it is not — that distinction is the whole of ticket 02's answer), and `ARCHITECTURE.md`'s rule count was wrong in both its old and proposed form, so it now names the two channels instead of a single drifting number.

- [Adversarial friction walk](issues/07-adversarial-friction-walk.md) — 13 findings against an installed tool. Worst: malformed YAML *inside* a well-formed frontmatter block crashed `check` — the command whose whole job is reporting frontmatter problems — with a traceback, exiting 1, indistinguishable from a normal findings exit. Also confirmed two things that held: nothing leaks outside the project root (`$HOME` diffed across all six harnesses plus `--ci`), and the `prompted_by:` cycle guard survives a hand-made 6-node cycle.
- [Fix what the walk found](issues/08-fix-the-friction.md) — 8 defects fixed, 5 design gaps left for decisions. 264 tests, up from 244. **The hook exit-code contract was broken and is now restored *and* hardened**: `report`'s "always 0" and `gate`'s "2 means findings exist" no longer hold only while smairt is bug-free — an internal failure now exits 0 / 1 respectively, never 2, because blocking every edit in a session because smairt itself broke would wedge the researcher out of their own work.

- [Close the five design gaps](issues/12-close-the-friction-walk-design-gaps.md) — all five decided by the researcher and implemented: `SMAIRT011` (project identity) plus fail-fast on unparseable config, with a message that prints a correct `smairt.yaml` so it is repairable by eye; `SMAIRT012` (README-less folder, warning); nesting warned at creation and named specifically by `SMAIRT006`; `SMAIRT013` (`prompted_by:` cycle, error); `--ref` validated at creation like `--from`. Review catches: a `../`-escaping `paths:` still passed clean (same defect as ticket 08's absolute-path bug, other spelling), and the config degrade policy had been made consistent by deleting the one warning that existed — now split on **reads versus writes**, so a write the researcher asked for never fails silently.

## Not yet specified

- **A generic notice channel on `ConnectResult`** — per-harness caveats
  (pi's trust prompt, Codex's restart requirement, OpenCode's lack of a slash
  command) have nowhere to surface today. A researcher on pi can have every file
  written correctly and still see no skills, because the trust prompt was never
  answered, and `connect` says nothing about it.

- **Whether `smairt status` / `smairt check` output itself reads well** to the floor
  audience — the daily surface, never yet judged against that reader.
- **Assistant-only path** (a scientist who has never opened a terminal): the
  direction, blocked on an install story — likely a PyPI release plus a
  one-command bootstrap.
- **What `.github/workflows/` should assert** once the demos and tutorials are gone;
  may fold into the deletion ticket, may earn its own.

## Out of scope

- **A worked end-to-end example / demo.** Ruled out by the Q4 charting decision:
  the 8 demos are deleted rather than ported. Noted honestly — this is the one
  place the doc decision pushes against the audience floor, since the floor reader
  gets a command reference and an assistant but no example of a question running
  through to an answer. Returns as a separate effort, ideally CI-tested so it
  cannot drift the way the deleted set did.
- **Implementing the assistant-only interface** — direction, not destination.
- **Distribution and identity** (PyPI, repo naming, version branding) — still
  deferred from [practical-smairt](../practical-smairt/map.md).
- **Native Windows support** — deferred; WSL is the path.
- **Scientific or biological analysis itself** — SMAIRT records the method, it does
  not do the science.
