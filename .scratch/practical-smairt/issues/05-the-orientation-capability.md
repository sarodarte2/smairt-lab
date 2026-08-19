# The orientation capability

Type: grilling
Status: resolved
Blocked by: 03, 04

## Question

What answers the returning researcher's four questions — what was I doing, what next, what routes exist, how did I get here? A CLI command (`smairt status`?), a generated view, a skill-mediated conversation, or a combination — and reading from which substrate? What does it show, and what does it refuse to show (to avoid becoming another long generated document)?

Includes the failure-mode preference: is it worse for SMAIRT to say "I can't tell what you were doing" or to confidently say the wrong thing?

## Answer

**`smairt status`** — one CLI command, also runnable by the assistant (the conversational layer is the same command, not separate state). Prints under one screen, entirely derived from STATUS.md + unit headers + Git:

- **Focus** and **next step** (from STATUS.md)
- **The spine**: each stage, frozen/active
- **Live questions**: open probes, dated
- **Recently closed**: last 2–3 verdicts, one line each
- **Warnings**: stale STATUS, broken evidence pointers

Nothing else — no history dump. Deep history is the unit trail and `background/`, reached by following the links status prints.

**Staleness handling (researcher's choice):** when drift is detected, status still shows the last intent but *labeled* — "STATUS last written Aug 5; these 3 folders changed since" — never claiming falsely, always saying exactly what to reconcile. It never silently invents intent and never withholds the researcher's own last words.
