---
name: smairt-new-project
description: Use when a researcher wants to start a new SMAIRT project, to interview them in plain language and run `smairt new` fully-flagged so they never have to type a raw prompt.
---

# SMAIRT New Project

The interview is the wizard. The researcher answers in their own words and
never needs to know a flag exists; explain any term they ask about in their
domain's language, not software language.

## Steps

1. Interview conversationally: the big question, project name, researcher
   name, one-line description, the researcher's own background, whether
   they expect to run on HPC, whether they expect this to support a paper,
   whether to initialize Git. Ask one or two questions at a time — never
   dump the whole form at once.
   - Big question: concrete and falsifiable, about one dataset or system,
     not a field. E.g. "Does denoising recover the true signal in low-SNR
     live-cell imaging, or does it invent structure?"
   - Background: two halves — field, plus how much of the computing side
     they want explained. The second half is what changes how you talk to
     them; a field name alone ("computational biology") changes nothing. If
     they answer with just a field, ask for the second half. E.g.
     "computational immunology; wet-lab background, not a programmer" or
     "clinical epidemiology; I write SQL, I don't write scripts".
   - Both are optional — skip either rather than inventing a placeholder; a
     skipped field is fine, a hollow one isn't.
   - Git: `--no-git` is a fully supported choice, not a lesser one — some
     researchers deliberately keep work local. The opt-out is recorded in
     `smairt.yaml`, so `smairt check` won't keep suggesting Git afterward.
2. Default the harness to whichever assistant is currently running this
   conversation, unless the researcher says otherwise.
3. Confirm the summary back in plain language, then run:
   ```
   smairt new --name "..." --researcher "..." --description "..." \
     --question "..." --expertise "..." \
     --harness ... --hpc/--no-hpc --paper/--no-paper --git/--no-git
   ```
   fully-flagged, so nothing prompts — this is the non-interactive contract
   the tests guard. Omit `--question`/`--expertise` outright when skipped.
4. If the researcher skipped the big question and wants it filled in later,
   edit `background/question.md` and `STATUS.md`'s `## Focus` by hand — when
   `--question` was passed, both are already correct and there's nothing to
   redo.
5. Hand off: suggest `smairt-new-question` for the first probe.

Never create the project folders by hand — `smairt new` is the sole
scaffold authority.
