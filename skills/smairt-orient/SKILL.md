---
name: smairt-orient
description: Use when joining or resuming a SMAIRT project session, to orient from the project's derived state before doing any work.
---

# SMAIRT Orient

Run `smairt status` first, always. It derives the project's state from unit
frontmatter and Git — never reconstruct where the project stands from
conversation memory, a prior session's summary, or assumption.

## Steps

1. Run `smairt status` (or `smairt status --json` if you need structured
   fields). It prints Focus, Next, the spine, live questions, recently
   closed questions, open questions, and any warnings/suggestions.
2. Read `STATUS.md` directly for the researcher's own words in Focus/Next/
   Open questions/Decisions.
3. Read the README of the 1–2 most recently touched units status points at
   (the active spine stage, the newest live or closed question) — not the
   whole project.
4. Restate to the researcher, in plain language: current focus, the next
   concrete step, and any open questions worth naming.
5. Surface every warning or suggestion `smairt status` reported (STATUS
   drift, receipt gaps, growth suggestions) — don't bury or summarize past
   them. If STATUS.md looks stale relative to what changed, say so plainly;
   never claim the project is where STATUS.md says it is when status has
   already labeled it stale.

Wait for the researcher to confirm or redirect the restated focus before
starting new work.
