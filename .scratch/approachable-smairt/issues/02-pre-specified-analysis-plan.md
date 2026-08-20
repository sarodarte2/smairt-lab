# The pre-specified analysis plan

Type: grilling
Status: resolved

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

## Answer

A required `## Analysis plan` body section on question units, asked for at
creation by the skill and enforced at close by `smairt check`. No new
frontmatter field.

### Correction to this ticket's premise

**This ticket claims hypothesis-before-run "is enforced at creation time." It is
not.** Verified empirically: `smairt unit new question --title "X"` with no
`--hypothesis` produces a unit that passes `smairt check` with **0 errors, 0
warnings**. `--hypothesis` is an optional flag, `units.py` fills `""`, and
`SMAIRT001` checks only that the *key exists*, never that it has content.
`SMAIRT007` (verdict non-empty on close) is the only non-empty check in the
entire rule set.

So the foundation this ticket was building on did not exist. **The hypothesis
gets fixed too**: an empty `hypothesis:` on a question unit becomes a `check`
error. The *flag* stays optional — you can create the unit and write the claim in
your editor a minute later. Making the flag mandatory would only train people to
type `--hypothesis "tbd"`.

### The plan: a body section, not a frontmatter field

`## Analysis plan`, in the question README's body. Chosen over a `plan:`
frontmatter line because a real plan reads *"compare treated vs. control on
normalized counts; call it real if the effect survives BH correction at q<0.05"*
— that does not fit on a YAML line, and forcing it produces `plan: standard
analysis`, which is worse than nothing because it looks like compliance.
`check.py` already parses `## Heading` body sections (`read_status` does it for
STATUS.md), so the rule reuses existing machinery.

### Required at close, not at creation

Non-empty before `status:` may move to a closed value — the same moment
`SMAIRT007` already fires, so it is one more field in a check the researcher is
already answering.

Rejected: **required at creation** — you do not always know the plan when you open
the question, and a hard gate there pushes people back to `mkdir`. Rejected:
**before the run, proven by Git** — scientifically the right moment, but not
honestly enforceable. It needs a commit between plan and run, `SMAIRT004`-style
Git checks are skipped entirely outside a work tree, and SMAIRT never commits on
the researcher's behalf. A rule that binds only the already-disciplined is not a
rule.

The mitigation is the project's own three-tier model (generated correctly >
checked mechanically > advised): **`smairt-new-question` asks for the plan during
the same conversation that sharpens the hypothesis**, before anything runs, so
the check at close is a backstop for the case where it never got written — not
the normal path.

### Amendments: kept, and machine-parseable

A changed plan keeps the original and appends a marked line:

```markdown
**Amended 2026-08-21:** switched to Bonferroni -- the tests aren't independent.
Original plan above stands otherwise.
```

`**Amended <date>:**` is readable to a person and greppable to a tool, so an
assistant reading the README cannot mistake a revised plan for the original. A
convention in `AGENTS.md` and the skills, not a check rule.

Explicitly refused: **erroring on an unamended plan change.** A rule that punishes
honest amendment teaches researchers to write vague plans that never need
amending, and a vague plan defeats the entire purpose. Recording *what changed and
why* is worth more than either a rigid plan or a silently rewritten one.

### Timing is NOT recorded — reversed during grilling

An earlier round recommended a frontmatter field disclosing whether the plan was
present at creation ("pre-specified") or added later. **Dropped, on the
researcher's objection, which was correct.**

The reasoning, kept because the same idea will resurface:

- Any two-valued label where one value is better **is a grade**. That is not a
  naming problem, so no neutral wording fixes it — the demerit is inherent to the
  information, since the only reason to record it is that one value is preferable.
- The field would be editable (consistent with "human edits are first-class"), so
  it is a self-report, not evidence.
- **The amendment marker already does the honest version, better**: it appears
  only when something actually changed, and says what and why in the researcher's
  own words.
- The map's discipline: complexity must be earned *and supervisable*. The observed
  problem is plan drift; the section plus the amendment convention address drift.
  A field measuring *how often you drifted* is a meta-feature, and the
  post-mortem's root failure was a tool outrunning the researcher's comprehension
  until supervision became rubber-stamping. A field whose only job is to grade the
  researcher's discipline is how a lab notebook starts feeling like an auditor.

Timing matters scientifically and cannot be enforced honestly, so SMAIRT states
the practice and records nothing.

### Scope

Question units only. A stage has no hypothesis and no verdict, so no plan.
Reference units are exempt — they are adopted pre-existing work, and demanding a
retroactive plan for it would be absurd.

### Consistency with ticket 01

Both tickets guard the boundary between what a unit set out to do and what it
reports. [Ticket 01](01-sidequest-lineage.md) scopes `verdict:` to the unit's own
`hypothesis:`; this ticket makes both the hypothesis and the decision rule
non-empty. Together: a question states its claim, states how it will be judged,
and answers only that claim.

### For the implementer (ticket 10)

New `check` rules needed: empty `hypothesis:` on a question unit, and a missing or
empty `## Analysis plan` section on a *closing* question unit. Both need new,
never-reused `SMAIRTNNN` ids and a row in `check.py`'s docstring table. The
question README body template gains the section; `smairt-new-question` and
`smairt-close-question` both change; `AGENTS.md` gains the amendment convention
and the verdict-scoping sentence from ticket 01.
