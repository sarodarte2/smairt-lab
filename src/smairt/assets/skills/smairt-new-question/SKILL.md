---
name: smairt-new-question
description: Use when starting a new exploratory probe in a SMAIRT project, to sharpen its hypothesis and analysis plan before any run and create it correctly.
---

# SMAIRT New Question

A question is one exploratory probe. Its hypothesis must exist before the
run — write it after and it's not a hypothesis, it's a rationalization.

## Steps

1. Read `background/question.md` first, before asking anything.
   - Real question in there: the probe should hang off it. Draft a
     candidate title and hypothesis from it and propose that draft to the
     researcher — don't ask them to produce one cold.
   - Still the `smairt new` placeholder: say so plainly and ask what the
     probe is instead. A probe can legitimately come before the big
     question exists; if one surfaces later, filling in
     `background/question.md` is a routine edit, not something to
     negotiate here.
   - Draft, don't interrogate, either way: propose something concrete for
     the researcher to react to. "No, it's not effect size, it's
     variance" is faster to say than composing a falsifiable hypothesis
     from a blank page — and a rejected draft is a success, it surfaces
     what they actually meant.
   - Ask one or two questions at a time — never dump the whole form at
     once.
   - An untestable hypothesis ("see whether X works") still gets pushed
     back on — that's this skill's scientific job and it doesn't soften.
     Do it by offering a falsifiable rewrite of what they said, not by
     rejecting their phrasing and asking them to try again.
   - Once the title and hypothesis are settled, move to the analysis
     plan — what they'll measure and how they'll decide — as its own,
     later beat, not alongside the hypothesis. Get at least a first draft
     before anything runs: this is the normal path, not a fallback;
     `smairt check` only catches a missing plan as a backstop, at close,
     when it never got written here.
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
