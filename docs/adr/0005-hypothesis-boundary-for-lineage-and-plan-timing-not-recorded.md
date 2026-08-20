# ADR 0005: The Hypothesis Test for Sidequest Lineage, and Why Plan Timing Is Not Recorded

Status: Accepted

## Context

Two related gaps showed up in the same audit of SMAIRT's scientific
conventions. First, a project's post-mortem (`.scratch/practical-smairt/issues/01-real-project-post-mortem.md`)
recorded a "scatter" failure: an unexpected result found mid-run gets chased
as a new dated question with no recorded link back to the unit that raised
it, so a reader can no longer tell the project's units grew out of each
other. Second, `smairt unit new question --hypothesis` was assumed to make
hypothesis-before-run an enforced guarantee; verified empirically, it did
not — `smairt check` (`SMAIRT001`) only confirmed the `hypothesis:` key
existed, never that it held a claim, so a unit created with no `--hypothesis`
at all passed clean. The same gap existed one level up: nothing recorded
what a researcher would measure or how they'd decide before the run, so an
analysis could drift to fit whatever the data turned out to show without
that drift ever being visible in the record.

Both gaps are the same shape: a claim, or the plan for judging it, needs to
exist *before* the evidence does, or the record can no longer distinguish a
real test from a story fitted to a result after the fact (HARKing —
Hypothesis After Results are Known). Frontmatter is a stable contract once
projects start depending on it, so the boundary chosen here needed to be
right the first time, not just plausible.

## Decision

A sidequest is not a new unit kind. It is an ordinary question unit that
records where it came from: an optional `prompted_by: <origin-folder>`
field, set via `smairt unit new question --from <origin>`, validated to
resolve at creation and re-checked by `smairt check` (`SMAIRT008`) for a
target that later goes stale. The field is never required — the rule fires
only when it is present and dangling.

`hypothesis:` becomes non-empty-checked (`SMAIRT009`), for any question
status, not just at close — the `--hypothesis` CLI flag stays optional, so a
researcher can still create a unit and write the claim in an editor a moment
later, but `smairt check` now holds that claim to actually existing before
treating any run as evidence.

A question README gains a `## Analysis plan` body section, positioned
directly after `## What we expected` — grouped with the other before-the-run
sections (`## Why ask this`, `## What we expected`), ahead of the
after-the-run sections (`## What happened`, `## What it means`, `## Next`).
It must be non-empty before a question can close (`SMAIRT010`, the same
moment `SMAIRT007` already requires `verdict:`) — not required at creation,
since a hard gate there would push researchers back toward `mkdir`-ing units
by hand. A changed plan keeps its original text and appends `**Amended
<YYYY-MM-DD>:** what changed and why` rather than being silently rewritten.
`AGENTS.md` states, in one sentence, that a unit's `verdict:` answers only
its own stated `hypothesis:` — an incidental finding belongs in its own
unit, never retrofitted into this one's verdict.

### Why the hypothesis test, not "does it need its own run?"

The first boundary proposed for sidequest lineage was effort-shaped: a
finding stays inline until following it up would require a new run. It has
a hole that matters more than it first looks: a researcher can be staring at
a figure already made, notice a batch effect in it, and form an entirely new
claim with **no new run at all** — just a second look at data already in
hand. Reanalyzing data that's already sitting there, under a claim formed
*after* seeing it, is exactly where HARKing lives. A test built on "needs a
new run" is silent precisely at the moment the danger is highest, because
the dangerous case is defined by the absence of a new run.

The hypothesis test — can you state the new claim in one testable line? —
does not have this hole, and it costs nothing extra to apply: `hypothesis:`
is already SMAIRT's defining field for a question unit, so the boundary is
"the moment you could write a `--hypothesis` for it, it is a `--hypothesis`
you should actually write, in its own unit." It is also the one test that
stays supervisable without training: "can you say the claim in one line?" is
answerable by anyone in the room, where "would this have needed a new run?"
requires guessing at a counterfactual.

### Why plan timing is not recorded

An earlier draft proposed a frontmatter field disclosing whether the
`## Analysis plan` was present at the unit's creation ("pre-specified") or
added later. It was dropped after the researcher pushed back, correctly.

Any two-valued label where one value is understood to be better than the
other is not a neutral fact — it is a grade. No amount of careful wording
fixes that, because the only reason to want the field at all is that one
value is preferable; the demerit is inherent to what the field measures, not
to how it is named. It would also be a self-report, not evidence: the same
"human edits are first-class" principle that makes frontmatter editable at
all makes a timing flag trivially back-datable, so it would carry the
appearance of rigor without the substance.

The amendment marker already produces the honest version of the same
information, and produces it better: it appears only when something
actually changed, in the researcher's own words, rather than reducing the
whole history of a plan to one bit chosen at write time. Complexity here
must be earned, and the problem actually observed is plan drift — a section
plus an amendment convention address drift directly. A field whose entire
purpose is to grade how disciplined the researcher was is a different kind
of feature: it measures the researcher, not the work, and a notebook that
starts scoring its author is a notebook that stops being trusted with
honest mistakes.

## Consequences

- `prompted_by:`, `hypothesis:`, and `## Analysis plan` all become part of
  the frontmatter/body contract `smairt check` enforces; existing projects
  with empty hypotheses or unfilled analysis plans on closed questions will
  see new findings the next time they run `smairt check`, with no
  auto-migration provided.
- A researcher who genuinely didn't have a plan before running still has an
  honest path to a clean check: write the plan now, reconstructed, and say
  so in prose — nothing punishes a late plan except its own absence, and the
  tool never claims to know when the plan was actually written.
- The verdict-scoping sentence in `AGENTS.md` is the entire mechanism
  guarding against a sidequest's finding contaminating its origin's verdict;
  there is no `smairt check` rule that can verify a verdict's prose stayed
  on-topic, so this protection is real only as far as an assistant or
  researcher actually reads and follows the contract.
- `results/INDEX.md` renders `prompted_by:` lineage as indentation with no
  new column; a chain of prompted questions nests correctly, and a dangling
  `prompted_by:` still renders its row (flat, at the top level) rather than
  being dropped, so `smairt check`'s `SMAIRT008` finding is always about a
  unit a researcher can still find in the index.
