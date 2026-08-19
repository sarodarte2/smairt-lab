# The research-state contract

Type: grilling
Status: resolved
Blocked by: 14

## Question

Should SMAIRT own machine-readable research state — tracks/routes, iterations, current focus, open questions, last decision — and if so: explicit (recorded at write time), derived (inferred from files/Git), or hybrid? Where does it live (`smairt.yaml`, `.smairt/`, a new tracked file), and what deliberately stays researcher-authored prose?

Today `smairt.yaml` holds identity, provenance, and capability toggles only; all research state is markdown convention. The orientation capability and cross-harness consistency both hang on this decision.

## Answer

**Hybrid, derived-first, with exactly one hand-updated state file.** The complete explicit inventory:

- **`smairt.yaml`** — identity only: name, researcher, description, scaffold version. Boring by design; changes rarely; never holds research state.
- **`STATUS.md`** at the project root — the single explicit state record: frontmatter-style block with *current focus* (one line), *next step* (one line), *open questions* (few bullets), and the rare project-level decision that belongs to no unit. This is the only file whose content cannot be derived, because it records **intent**.
- **Everything else is derived**: routes, unit statuses, dead ends, and the decision trail are reconstructed from unit README frontmatter headers plus Git history. Decisions live where they were made — a `decision:` field in the frontmatter of the stage/question that settled them; STATUS.md catches only the homeless ones. No BREADCRUMB_TRAIL, no ITERATION_LOG, no session_log, no tracks table. Net file count *falls*.

**The maintenance system (researcher's requirement: automated, not honor-based):**
1. `smairt check` gains a **status-drift rule**: STATUS.md older than the newest change under `pipeline/` or `questions/` = drift, reported with the files that outran it.
2. **Harness stop/session-end hooks** (all five harnesses support them, per the harness survey) run that check; on drift, the hook feeds back into the session so the assistant proposes a three-line STATUS.md diff *before finishing*. The human's entire role is approving that diff.
3. **CI runs the same check** as the floor that binds regardless of local hook config.

The trigger is therefore mechanical (drift detection), the writing is delegated (assistant proposes), and the human contributes only the thing only they have: confirming intent.
