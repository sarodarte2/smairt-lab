---
name: smairt-new-question
description: Use when starting a new exploratory probe in a SMAIRT project, to sharpen its hypothesis before any run and create it correctly.
---

# SMAIRT New Question

A question is one exploratory probe. Its hypothesis must exist before the
run — write it after and it's not a hypothesis, it's a rationalization.

## Steps

1. Sharpen the title and hypothesis WITH the researcher, in conversation,
   before creating anything. A vague title or an untestable hypothesis is
   worth pushing back on now, not after the unit exists.
2. Create the unit with:
   ```
   smairt unit new question --title "..." --hypothesis "..."
   ```
   Add `--receipt --tool ... --tool-version ... --command ...` when the
   probe wraps an outside tool rather than the project's own code. Never
   `mkdir` the folder by hand — the command is the sole numbering, dating,
   and skeleton authority.
3. Fill in the generated README's `## Why ask this` and
   `## What we expected` sections before the run happens. Leave
   `## What happened`, `## What it means`, and `## Next` for
   smairt-close-question once evidence exists.
4. If this hypothesis spans more than one probe, note it as a bullet in
   `STATUS.md`'s Open questions per AGENTS.md — a routine proposal.
