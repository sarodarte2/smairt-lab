---
name: smairt-new-project
description: Use when a researcher wants to start a new SMAIRT project, to interview them in plain language and run `smairt new` fully-flagged so they never have to type a raw prompt.
---

# SMAIRT New Project

The interview is the wizard. The researcher answers in their own words and
never needs to know a flag exists; explain any term they ask about in their
domain's language, not software language.

## Steps

1. Interview conversationally: the research question, project name,
   researcher name, one-line description, whether they expect to run on
   HPC, whether they expect this to support a paper. Ask one or two
   questions at a time — never dump the whole form at once.
2. Default the harness to whichever assistant is currently running this
   conversation, unless the researcher says otherwise.
3. Confirm the summary back in plain language, then run:
   ```
   smairt new --name "..." --researcher "..." --description "..." \
     --harness ... --hpc/--no-hpc --paper/--no-paper
   ```
   fully-flagged, so nothing prompts — this is the non-interactive contract
   the tests guard.
4. With the researcher's approval, seed `STATUS.md`'s Focus/Next and
   `background/question.md` from the interview — both already exist from
   `smairt new`, but with placeholder text you can now replace with the
   real research question.
5. Hand off: suggest `smairt-new-question` for the first probe.

Never create the project folders by hand — `smairt new` is the sole
scaffold authority.
