# The sidequest and unit lineage

Type: grilling
Status: open

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
