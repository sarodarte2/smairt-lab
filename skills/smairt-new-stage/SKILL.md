---
name: smairt-new-stage
description: Use when adding a new step to a SMAIRT project's spine, to tell durable spine work apart from a one-off probe and create it correctly.
---

# SMAIRT New Stage

A stage is one step of the spine — durable work the project's story depends
on, not a side probe (use smairt-new-question for that instead).

## Steps

1. Decide with the researcher whether this is genuinely spine work. If it's
   exploratory or its outcome is uncertain, it's probably a question, not
   a stage.
2. Create it with:
   ```
   smairt unit new stage --title "..."
   ```
   Add `--receipt --tool ... --tool-version ... --command ...` if it wraps
   an outside tool. Never `mkdir` the folder by hand — the command is the
   sole numbering authority, and numbered folders sort above dated ones so
   the spine reads top-down.
3. Fill in the generated README's `## Purpose` (what this stage settles)
   and `## Approach` (the script or method, updated if it changes).
4. If the stage holds alternatives, keep them as sibling variant
   subfolders inside it (e.g. `deseq2/`, `limma/`). Once one wins, record
   the active variant and why the others lost in `## Result`.
5. Freezing a stage (`status: frozen`) is a **structural** proposal under
   AGENTS.md's stakes rule — explain it per the explanation rule and get
   the researcher's explicit yes before making the change.
