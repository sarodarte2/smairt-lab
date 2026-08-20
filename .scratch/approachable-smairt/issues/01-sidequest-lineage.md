# The sidequest and unit lineage

Type: grilling
Status: resolved

## Question

A researcher opens a question unit with a hypothesis. Mid-run, an unexpected or
interesting result appears and they chase it — an exploratory sidequest that was
never the thing being tested.

SMAIRT today has no way to record any of that. The sidequest becomes either an
untracked detour or a second dated question with no link back to the one that
spawned it. Two distinct harms follow, and the ticket must address both:

1. **Lost lineage.** A reader cannot tell that the second unit exists *because of*
   the first. The project scatters into dated folders whose relationships live
   only in the researcher's memory — the "scatter" failure recorded in
   [the real-project post-mortem](../../practical-smairt/issues/01-real-project-post-mortem.md).
2. **Contaminated verdict.** The incidental finding gets retrofitted into the
   original hypothesis's `verdict:`, so a result the study did not set out to test
   is reported as though it had been. This is HARKing, and SMAIRT currently offers
   no friction against it — arguably it makes it easier, since one README holds
   both the hypothesis and the interpretation.

Decide: how is a sidequest recorded, how is its relationship to its originating
unit expressed, and what mechanism keeps the incidental finding out of the
original unit's verdict?

Constraints from the map's Notes apply: complexity must be earned *and*
supervisable. A new frontmatter field with a `smairt check` rule is cheap; a new
unit kind, a graph, or a parent/child hierarchy is expensive and must justify
itself against the two harms above.

Things the resolution should settle:

- Is a sidequest a new unit, a section inside the existing one, or either
  depending on size? What is the test for which?
- How is lineage expressed — a `spawned_from:` pointer, a `related:` list,
  something else? Does it point up, down, or both?
- Does `smairt check` enforce anything here, or is this guidance in `AGENTS.md`?
- Does `results/INDEX.md` or `smairt status` need to show lineage, and if so how
  without becoming a graph the researcher cannot read at a glance?
- Does the original unit's verdict need to state its scope explicitly
  ("this verdict covers the stated hypothesis only")?

Per `/domain-modeling`: whatever this relationship is called, write the term into
`CONTEXT.md` as it resolves. The glossary currently has no word for it.

## Answer

A sidequest is **not a new unit kind**. It is an ordinary question unit that
records where it came from. The design is one frontmatter field, one creation
flag, one check rule, and one sentence in `AGENTS.md`.

### The boundary: the hypothesis test

A finding stays inside the originating unit until you can **state a new testable
claim in one line**. At that moment it becomes its own question unit.

Chosen over "does it need its own run?", which was the first proposal and has a
hole: you can be looking at a figure you already made, notice a batch effect, and
form a new claim with **no new run at all**. Reanalyzing data already in hand,
under a claim formed after seeing it, is exactly where HARKing lives — so the run
test is silent precisely where the danger is highest. The hypothesis test is
stricter in the right place, and it is already SMAIRT's own boundary: `hypothesis:`
is the defining field of a question unit. It stays supervisable, too — "can you
write the new claim in one line?" is answerable by anyone, and if the answer is
yes, they have just written the unit's `--hypothesis`.

Rejected: an effort/time threshold (measures cost, not science) and "changes what
you'd do next" (only judgable in hindsight, which is too late to record).

### The link: `prompted_by:`, child to parent

The new question carries `prompted_by: <origin unit folder name>`, set at
creation:

```
smairt unit new question --title "..." --hypothesis "..." --from 2026-08-20_why-is-signal-low
```

Child-to-parent, not parent-to-child or both: the child knows its origin the
moment it is created, while the parent does not know its children until later —
so a parent-side list means going back to edit a unit that may already be closed,
which is friction arriving at the worst possible moment. Because
`results/INDEX.md` is derived, the single child-side pointer is enough to render
the whole tree with nobody maintaining it.

Named `prompted_by:` rather than `spawned_from:` — the latter is tech jargon and
this project's reader is a scientist. `--from` is the flag.

**The glossary gains a relationship, not a noun.** There is no fourth unit kind;
"sidequest" stays a working word and does not enter `CONTEXT.md`.

### The contamination guard

`AGENTS.md` states that a unit's `verdict:` answers **its own stated
`hypothesis:` and nothing else**. A finding that is not about that line does not
belong in that verdict — it belongs in its own unit's verdict. One sentence, no
new machinery.

Rejected: a separate `incidental:` field. It sounds tidy but would ship a field
with no consumer and no rule, and an unused field gets filled with junk or
ignored. Earn it later from a case where the contractual statement demonstrably
failed.

### Enforcement

A new `smairt check` rule: a `prompted_by:` that does not resolve to a real unit
is an **error**, the same class of defect as a dangling `script:`/`log:` pointer,
reusing the pointer-resolution machinery `check.py` already has.

**Nothing ever requires the field.** The rule fires only when `prompted_by:` is
present and points nowhere, so it never nags a researcher who does not use it.
Explicitly refused: any rule of the form "this question looks like it came from
somewhere, go link it" — unenforceable, and it would train researchers to ignore
`smairt check`, which is how the previous iteration's conventions decayed.

`--from` validates at creation and fails fast, consistent with every other
creator.

### Rendering

`results/INDEX.md` nests a prompted question's row **under its origin, as
indentation** — no new column. That document's whole job is showing how evidence
hangs together, and a prompted question whose origin is invisible there recreates
the scatter problem in the one file meant to solve it.

`smairt status` does **not** show lineage. It answers "where am I now," and groups
questions by live vs. closed — the more useful axis when resuming. A second
grouping on one screen makes it worse.

No new README body section: `## Why ask this` already holds the prose half.

### For the implementer (ticket 10)

This is hard to reverse (frontmatter is contract), surprising without context (why
the hypothesis test and not the run test), and the result of a real trade-off —
**write an ADR** alongside the implementation.
