---
name: smairt-new-question
description: Use when starting a new exploratory probe in a SMAIRT project, to sharpen its hypothesis and analysis plan before any run and create it correctly.
---

# SMAIRT New Question

A question is one exploratory probe. Its hypothesis must exist before the
run — write it after and it's not a hypothesis, it's a rationalization.

## Steps

1. Sharpen the title and hypothesis WITH the researcher, in conversation,
   before creating anything. A vague title or an untestable hypothesis is
   worth pushing back on now, not after the unit exists. In the SAME
   conversation, also ask what they'll measure and how they'll decide —
   the analysis plan — and get at least a first draft of it before anything
   runs. This is the normal path, not a fallback: `smairt check` only
   catches a missing plan as a backstop, at close, when it never got
   written here.
2. If this question exists because of something another unit's result
   showed — a batch effect noticed in a figure, an unexpected value in a
   log — that's `--from <origin-unit-folder>`, not a note buried in this
   question's `## Why ask this`. The boundary is the hypothesis test: the
   moment you can state the new claim in one line, it's its own unit.
3. Create the unit with:
   ```
   smairt unit new question --title "..." --hypothesis "..." [--from ORIGIN_FOLDER]
   ```
   Add `--receipt --tool ... --tool-version ... --command ...` when the
   probe wraps an outside tool rather than the project's own code. Never
   `mkdir` the folder by hand — the command is the sole numbering, dating,
   and skeleton authority.
4. Fill in the generated README's `## Why ask this`, `## What we expected`,
   and `## Analysis plan` sections before the run happens. Leave
   `## What happened`, `## What it means`, and `## Next` for
   smairt-close-question once evidence exists.
5. If this hypothesis spans more than one probe, note it as a bullet in
   `STATUS.md`'s Open questions per AGENTS.md — a routine proposal.
