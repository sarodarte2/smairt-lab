---
name: smairt-adopt
description: Use right after `smairt adopt` runs, to walk a pre-existing project's folders and propose reference units for what matters — one folder, one approval, at a time.
---

# SMAIRT Adopt

`smairt adopt` already laid the contract files around this project and moved
nothing. Your job now: help the researcher decide which existing folders earn
a reference unit — never touch the folders themselves.

## Steps

1. Run `smairt status` (or read `smairt.yaml`'s `adoption.known_folders:`) to
   get the list of top-level folders that predate SMAIRT.
2. Present that list to the researcher plainly. Ask which folder to look at
   first — don't assume an order.
3. For ONE folder at a time: look at what's inside, and if it holds real
   research work (not just scratch or vendor files), PROPOSE a reference unit.
   This is a **structural** proposal under AGENTS.md's stakes rule — get the
   researcher's explicit yes before creating it. Follow the explanation rule:
   say (a) what the unit will point at, (b) what's lost by not proposing one
   here (the work stays invisible to `smairt status`/`results/INDEX.md`), (c)
   the alternative (leave it unreferenced for now) and why you're not just
   doing that.
4. On a yes, create it with:
   ```
   smairt unit new question --title "..." --ref path/to/folder
   ```
   (or `stage` if it is a step of an ongoing spine, not a one-off probe).
   Never `mkdir` it and never move or rename the referenced folder — the
   `--ref` unit is a pointer, not a container.
5. Fill in the generated README's "What this references and why it matters"
   section with the researcher, in their words.
6. Move to the next folder only after this one is settled. Stop as soon as
   the researcher says enough — an incomplete walk is fine; nothing here is
   time-boxed or required to finish in one sitting.
7. Run `smairt check` after each new unit to confirm its `paths:` pointer
   resolves.
