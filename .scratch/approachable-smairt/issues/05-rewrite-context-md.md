# Rewrite CONTEXT.md in the vocabulary the tool actually uses

Type: task
Status: resolved

## Question

`CONTEXT.md` is the domain glossary that `docs/agents/domain.md` tells every
engineering skill to read before exploring the codebase. It is entirely v1.

Verified: it defines *screen*, *framed screen*, *semantic palette*, *action
token*, *capability*, *capability selection*, *diff preview*, *scaffold
blueprint*, *starting phase*, *current phase*, *golden project* — machinery that
the `v2-rebuild` demolition removed. It contains **zero** occurrences of *stage*,
*question*, *spine*, *receipt*, *verdict*, *harness*, *evidence pointer*, or
*dataset* — the words the tool now runs on. Every skill that reads it is being
handed the vocabulary of a dead program.

Rewrite it as an accurate v2 glossary.

Scope and constraints:

- It stays **agent- and contributor-facing**, per `docs/agents/domain.md` — it is
  not a scientist-facing document, and not the place to be approachable. That job
  belongs to [the README](06-split-the-readme.md).
- Per domain-modeling: `CONTEXT.md` is **a glossary and nothing else**. No
  implementation detail, no spec, no scratch notes. The existing "Core
  Relationships" and "Invariants" sections should be re-derived for v2 or dropped
  — decide which, and say why in the commit.
- Terms to cover, at minimum: unit, stage, question, reference unit, receipt,
  spine, evidence pointer, verdict, frontmatter, finding, suggestion, rule,
  harness, harness wiring, bridge file, dataset, dataset location, adoption,
  project root, golden fixture.
- Source the definitions from the code and `docs/ARCHITECTURE.md`, not from the
  old glossary's phrasing.

**Sequencing note:** tickets [01](01-sidequest-lineage.md) and
[02](02-pre-specified-analysis-plan.md) each introduce a new domain term and, per
domain-modeling, write it into `CONTEXT.md` as they resolve. This ticket is not
blocked on them — it removes the v1 vocabulary and establishes the v2 baseline —
but whoever runs it should re-read `CONTEXT.md` first in case those terms have
already landed, and must not clobber them.

## Answer

Rewritten. 25 terms, all sourced from the v2 code rather than reworded from the
dead glossary: Unit, Stage, Question, Reference unit, Spine, Hypothesis, Analysis
plan, Prompted by, Verdict, Receipt, Evidence pointer, Frontmatter, Finding,
Suggestion, Rule, Contract, Harness, Harness wiring, Bridge file, Skill, Dataset,
Dataset location, Adoption, Project root, Golden fixture.

Zero occurrences remain of *screen*, *palette*, *blueprint*, *capability*, or
*phase*. The `Analysis plan` and `Prompted by` rows survived verbatim, as
required — only their position changed.

**Core Relationships and Invariants dropped, not re-derived.** Both were
spec-shaped assertions rather than definitions, and domain-modeling is explicit
that `CONTEXT.md` is a glossary and nothing else. Re-deriving v2 equivalents
would create a second, informal description of what `docs/ARCHITECTURE.md` and
each module docstring already state authoritatively — a second source of truth
that drifts. Agreed.

**`Contract` added** beyond the ticket's list: the code uses it pervasively
(`check.py`'s "the state contract", `connect.py`'s "the one contract — AGENTS.md")
and both Harness wiring and Adoption needed to reference it.

### Two accuracy fixes on review

1. **`Rule` claimed there were ten**, covering only `SMAIRT001`–`SMAIRT010`. The
   advisory rules `SMAIRT101`–`SMAIRT105` are rules too — `check.py`'s own section
   headers number them alongside the rest. Rewritten to cover both channels and
   to state that the rule, not each way of violating it, is the unit of identity.
2. **`Evidence pointer` read "Unresolved once a unit is closed"**, which doesn't
   parse and inverts the actual behavior. Rewritten to the real rule: a closed
   unit is held to the strict reading (file exists, `script:`/`log:` non-blank);
   an open unit's not-yet-run `log:` counts as resolved while its folder exists,
   which is what lets a fresh question pass. Also added the genuine gotcha that
   `paths:` resolves from the project root while every other pointer resolves
   from the unit folder.

The `smairt data locate` idempotency claim was checked against `add_location`
rather than taken on trust — accurate.
