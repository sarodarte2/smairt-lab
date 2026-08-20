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
2. Check `## Analysis plan`. If it's still empty, it should have been
   written before the run (smairt-new-question) — write it now from
   memory of what was intended, and say so; don't fabricate a plan as if
   it had been there all along. If the actual analysis diverged from what
   was written for a real reason, keep the original text and append
   `**Amended <YYYY-MM-DD>:**` plus what changed and why — never rewrite
   the plan silently. `smairt check` requires this section non-empty
   before a question can close.
3. Write `## What happened` in the unit README as facts only — what the
   log or output actually shows, nothing inferred.
4. Write `## What it means` separately, as your interpretation. Every
   claim in this section must point at the specific log line, output file,
   or figure that backs it — per AGENTS.md's evidence rules, no unsourced
   claims. A finding that isn't about this unit's own `hypothesis:` doesn't
   belong here — it's a new question (smairt-new-question, `--from` this
   unit), not a footnote on this verdict.
5. In the same edit, set `status:` to the outcome (`supported`, `refuted`,
   `inconclusive`, or `dead-end`) and fill `verdict:` with a one-line
   summary that answers only the stated `hypothesis:`. `smairt check`
   requires `verdict:` and `## Analysis plan` both filled for a closed
   question.
6. Propose a 3-line STATUS.md update (focus / next / one open question)
   per AGENTS.md's practices, and apply it once the researcher agrees.
7. Run `smairt check` and confirm it passes before ending the session.
