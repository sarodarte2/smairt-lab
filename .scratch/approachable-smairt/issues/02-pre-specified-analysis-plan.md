# The pre-specified analysis plan

Type: grilling
Status: open

## Question

`smairt unit new question --hypothesis "..."` already forces the hypothesis to
exist before the run — that much is enforced at creation time.

What is *not* captured is what the researcher said they would **measure** and how
they would **decide**. Without it, the analysis can drift to fit the data it saw,
and nothing in the record shows that it did. Hypothesis-before-run without
analysis-plan-before-run is only half the guarantee.

Decide: what records the analysis plan, and how strictly is it held?

Things the resolution should settle:

- **Shape.** One frontmatter field (`plan:`), a required README body section, or
  both? Frontmatter is machine-checkable and shows up in
  `results/INDEX.md`; a body section holds more nuance but only prose-checks.
- **Required or optional?** Required on every question unit is the strong version
  and the annoying one. Optional means it will be skipped exactly when it matters.
  Is there a middle — required to *close* a question, not to open one?
- **What `smairt check` enforces.** Non-empty? Present before the unit's log
  exists (i.e. written before the run, the thing that actually matters)? The
  before-the-run check is the scientifically meaningful one and also the harder
  one — does Git make it feasible, the way rule SMAIRT004 uses Git for log
  immutability?
- **Deviation.** Real research changes its plan for legitimate reasons. Is a
  changed plan an error, or a recorded amendment with a reason? A rule that
  punishes honest amendment will train researchers to write vague plans.
- **Relationship to the verdict.** Should closing a question require stating
  whether the analysis followed the plan?

Interaction with [The sidequest and unit lineage](01-sidequest-lineage.md): both
tickets touch the boundary between what a unit set out to do and what it ended up
reporting. Resolve them consistently — check the other's answer before finalizing.

Per `/domain-modeling`: add the resolved term to `CONTEXT.md` inline.
