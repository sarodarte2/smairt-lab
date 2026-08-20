# Practical SMAIRT — wayfinder map

Label: wayfinder:map

## Destination

**REACHED (2026-08-19).** A decided design record — `.scratch/practical-smairt/spec.md` — where every major decision carries its rationale and evidence, complete enough that an implementation effort can rebuild SMAIRT's researcher-facing surface in about one week, so the researcher's real project runs inside SMAIRT the week after. All 14 tickets resolved; the spec is written as six subagent-executable work packages (WP0 demolition, WP1 scaffold/units, WP2 check, WP3 status, WP4 harness wiring, WP5 AGENTS.md + skills, plus the `smairt adopt` stretch goal).

## Notes

- Skills each session should consult: `/grilling` + `/domain-modeling` (via `/grill-with-docs`) for HITL tickets; `/improve-codebase-architecture` only after the major tensions are settled — its first output is options and tradeoffs, never an implementation.
- Standing preferences: at most 3 questions per round, multiple-choice preferred; **complexity must be earned** (every proposed mechanism answers "what observed problem requires this?"); do not code, refactor, or branch during this effort; the user co-developed SMAIRT and is a practicing scientist — challenge their assumptions, don't defer, and don't replace their judgment.
- Audience decision (charting round): design for computational researchers now (git/CLI/Python-comfortable), without foreclosing "any scientist with an AI assistant" later.
- Evidence source (charting round): the user's ongoing real research was **forced out of SMAIRT** — files became convoluted, everything mixed. That project (or its reconstruction) is the primary evidence; repo demos are synthetic.
- Timeline: design record this week; implementation next; real research resumes in SMAIRT the week after.
- Evidence anchors already established: `docs/history/adversarial_review1.md` (prior collapse/recovery cycle — several handout "unknowns" have recorded answers there); `CONTEXT.md` glossary defines ~20 tool/TUI terms and no scientific ones; eight overlapping "where are we" records in the scaffold; ~63% of the Python is interactive presentation; README/QUICKSTART point at `PNNL-CompBio/smairt-template` while the remote is `sarodarte2/smairt-lab`, and "V0.1" branding coexists with version 0.4.0.

## Decisions so far

<!-- one line per closed ticket: gist + link -->

- [Survey: harness guidance conventions](issues/10-survey-harness-guidance-conventions.md) — one canonical `AGENTS.md` reaches every major harness (Claude Code via a 2-line `@AGENTS.md` bridge); instruction files are advisory everywhere, but all five harnesses expose a blocking pre-tool-use hook a `smairt check`-style CLI could plug into, with CI as the only universal enforcement floor.
- [Survey: comparable frameworks](issues/11-survey-comparable-frameworks.md) — surviving frameworks derive state from files + Git with at most one small explicit config; structure is user-grown by convention with rigor checked only at the sharing boundary; day-one scaffolding weight is a documented abandonment cause (Kedro's own user research); re-orientation is the least-solved problem in every file-based framework surveyed.
- [Real-project post-mortem](issues/01-real-project-post-mortem.md) — the real DE/RNA-seq project left SMAIRT within days; root failure is **supervision collapse** (complexity outran comprehension, approval became rubber-stamping, driven by standing + missing explanation + undifferentiated stakes), then work-shape mismatch (spine pipeline + probe branches vs. the single "iteration" unit), ledger overload, convention decay, scatter; **nothing in the scaffold demonstrated value** — principles must be re-derived from the philosophy, and the design must be supervisable by any scientist, not just computational ones. The binding design constraint is the researcher's comprehension budget: complexity must be supervisable, not merely earned.
- [The one-week scope](issues/02-the-one-week-scope.md) — the spec commits to five items (work-unit model, minimal scaffold, state contract, orientation, one canonical AGENTS.md + `smairt check`), sliced into subagent-executable mini-handouts; distribution/identity deferred until after a solo stress-test, then PNNL sharing, then main-branch decisions.
- [TUI economics](issues/13-tui-economics.md) — shrink: prompt-based `smairt new` replaces the fourteen-screen wizard; dashboard/framed-screen machinery not carried forward; full remake acceptable; the daily surface is the harness/IDE.
- [Phase trichotomy: principle or accident](issues/07-phase-trichotomy-principle-or-accident.md) — accident as structure, principle as practice: tripled phase trees removed; "cheap data first" survives as per-dataset provenance metadata plus recommended practice in the canonical guidance.
- [The work-unit model](issues/14-the-work-unit-model.md) — exactly two units: **stages** (`pipeline/NN_name/`, ordered, freezable) and **questions** (`questions/DATE_name/`, README = hypothesis + interpretation); YAML frontmatter headers make all state derivable cheaply; dead ends marked in place, never moved; contained forks as in-stage variant subfolders, propagating forks as visible tail duplication; the fork transition is the first concrete case for the growth-proposal mechanism.
- [The research-state contract](issues/03-the-research-state-contract.md) — hybrid, derived-first: `smairt.yaml` = identity only; one root `STATUS.md` holds intent (focus / next / open questions / homeless decisions); everything else derived from unit headers + Git; kept honest by a mechanical system — `smairt check` status-drift rule, wired into harness stop hooks (assistant proposes the three-line update, human approves) with CI as the floor.
- [Consolidating the guidance surfaces](issues/08-consolidating-the-guidance-surfaces.md) — three tiers: generated correctly (tool-written README skeletons) > checked mechanically (`smairt check` + hooks) > advised (one ~1-page AGENTS.md with an appendable project-learnings section); procedures live in multiple small SMAIRT-owned skills shipped with the tool; priming prompts and the seven other guidance files die; hooks installed when the researcher selects a harness.
- [The cross-harness contract](issues/09-the-cross-harness-contract.md) — consolidated: canonical AGENTS.md + generated bridges; skills for procedures; enforcement = `smairt check` via per-harness hooks + CI floor; a new harness costs one bridge + one hook template.
- [Consolidating the state records](issues/04-consolidating-the-state-records.md) — consolidated: all eight old ledgers die or merge into unit READMEs; survivors are `smairt.yaml`, `STATUS.md`, unit READMEs; `intellectual_contribution.md` deferred to the anti-bias ticket, `STUDY_REPORT` to spec work as a derived on-demand synthesis.
- [Day-one scaffold weight](issues/06-day-one-scaffold-weight.md) — ten-item scaffold locked (identity, STATUS, AGENTS + bridge, background/, data/, `scripts/` shared code, single `experiments/`, generated results/INDEX.md); units self-contained with standard `logs/`/`out/`/`figures/`; analysis merged into unit READMEs; hypotheses at two levels; three unit cases (own code / outside-tool receipt / adopt), receipts born as fill-in forms and covering shared-script invocations (anti-LLM-rewrite mechanism); growth = creation opt-ins + mechanical detection + proposal-gated additions; warnings default, blocking optional; human edits first-class; `smairt adopt` a stretch goal.
- [The orientation capability](issues/05-the-orientation-capability.md) — `smairt status`: one derived, under-a-screen view (focus/next, spine, live questions, recent verdicts, warnings); assistant runs the same command; stale intent is shown but labeled with exactly what to reconcile — never false, never withheld.
- [Minimum anti-bias mechanism](issues/12-minimum-anti-bias-mechanism.md) — three mechanisms only: stakes labels (routine/notable/structural, only structural needs explicit yes), the explanation rule (what/scientific risk/one alternative, in plain language — absorbs intellectual_contribution.md), and a researcher-invoked adversarial-review skill.

## Not yet specified

- **Study report / cross-experiment synthesis** — spec work: likely an on-demand derived synthesis command, not a maintained file.
- **Paper and HPC capability fate** under the new scaffold shape.
- **Tutorial, demo, and skill updates** to match whatever is decided.
- **Dissertation-facing rationale** — expected to fall out of the decision records rather than need separate work.

## Out of scope

- **Implementing the design** — the destination is the spec; the build is a follow-on effort.
- **Scientific or biological analysis** — workflow examples only.
- **New databases, plugin systems, or scheduler integration** — ruled out by the handout's complexity discipline unless a ticket proves a concrete need.
- **Distribution and identity** (repo naming mismatch, V0.1-vs-0.4.0 confusion, PyPI) — deferred by [The one-week scope](issues/02-the-one-week-scope.md): this week's audience is the researcher stress-testing alone; public identity is fixed at the PNNL-sharing gate, a follow-on effort.
- **Full migration/adoption of existing projects** — deferred by [Day-one scaffold weight](issues/06-day-one-scaffold-weight.md): `smairt adopt` is specified (contract-around, move-nothing, proposal-gated) but built only as a stretch goal; PNNL's complex existing projects adopt after the shape survives the researcher's fresh-start stress test.
