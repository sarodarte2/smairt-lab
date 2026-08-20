---
name: smairt-close-question
description: Use when closing a SMAIRT question unit, to separate facts from interpretation, record a verdict, and touch STATUS.md.
---

# SMAIRT Close Question

Closing a question means the log exists and the probe has an answer, even
if the answer is "inconclusive."

## Steps

1. Read the unit's log(s) in `logs/` directly. Do not interpret from
   memory or from what you expected to see.
2. Write `## What happened` in the unit README as facts only — what the
   log or output actually shows, nothing inferred.
3. Write `## What it means` separately, as your interpretation. Every
   claim in this section must point at the specific log line, output file,
   or figure that backs it — per AGENTS.md's evidence rules, no unsourced
   claims.
4. In the same edit, set `status:` to the outcome (`supported`, `refuted`,
   `inconclusive`, or `dead-end`) and fill `verdict:` with a one-line
   summary. `smairt check` requires both together for a closed question.
5. Propose a 3-line STATUS.md update (focus / next / one open question)
   per AGENTS.md's practices, and apply it once the researcher agrees.
6. Run `smairt check` and confirm it passes before ending the session.
