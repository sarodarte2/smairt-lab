# Consolidating the state records

Type: grilling
Status: resolved
Blocked by: 03

## Question

The scaffold ships at least eight overlapping "where are we" records: `ITERATION_LOG.md` (current-state table plus outcome history), `BREADCRUMB_TRAIL.md`, `prompts/session_log.md`, `ANALYSIS_PLAN.md` (tracks table), `STUDY_REPORT.md`, `prompts/intellectual_contribution.md`, per-iteration `ANALYSIS_NN.md`, and hypothesis status fields. Each rots independently and each depends on an AI or human remembering to write it.

Which survive as canonical, which merge, which become derived views of the research-state contract, and which die? An orientation feature added without this consolidation is a ninth record.

## Answer (consolidated — the fates all follow from the work-unit model and state-contract decisions)

| Old record | Fate |
|---|---|
| `ITERATION_LOG.md` (table + history) | Dies; the timeline is derived from unit frontmatter + Git history |
| `BREADCRUMB_TRAIL.md` | Dies; reasoning lives in the unit READMEs where it happened |
| `session_log.md` | Dies; STATUS.md carries intent between sessions |
| `ANALYSIS_PLAN.md` tracks table | Dies; routes are derived from stage/variant/question headers |
| Hypothesis files + status fields | Merge into question READMEs (the README *is* hypothesis + interpretation) |
| Per-unit `ANALYSIS_NN.md` | Merges into its question/stage README |
| `intellectual_contribution.md` | Deferred to the anti-bias ticket — the one record whose fate isn't mechanical |
| `STUDY_REPORT.md` | Deferred to spec work: likely an on-demand *derived* synthesis, not a maintained file |

Surviving explicit records: `smairt.yaml` (identity), `STATUS.md` (intent), unit READMEs (the science). Everything else is a view.
