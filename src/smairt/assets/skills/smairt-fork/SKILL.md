---
name: smairt-fork
description: Use when a SMAIRT project's work forks into competing alternatives, to decide whether the fork is contained or propagating and record it correctly.
---

# SMAIRT Fork

Forks are visible in the folder structure, never hidden in Git branches —
a reader must be able to see the fork just by looking.

## Two shapes

**Contained fork** — alternatives tried within one stage. Create sibling
variant subfolders inside that stage's folder (e.g. `deseq2/`, `limma/`).
The stage README records the active variant and why the losing ones lost.
This is a **notable** proposal under AGENTS.md's stakes rule.

**Propagating fork** — the fork changes downstream stages too, not just
this one. Duplicate the affected spine tail as variant-named stage
folders, created one at a time with:
```
smairt unit new stage --title "..."
```
Never `mkdir` a variant stage by hand. This is **structural**: get the
researcher's explicit yes first, explained per the explanation rule —
(a) what duplicating the tail does, (b) what it risks scientifically
(e.g. drift between variants, doubled maintenance), (c) one alternative
(e.g. staying contained a while longer) and why not.

## Steps

1. Decide with the researcher which shape this is — contained stays
   inside one stage; propagating touches more than one.
2. Apply the matching mechanism above.
3. Update the affected README(s) so the active variant and the losing
   reasoning are recorded before moving on.
