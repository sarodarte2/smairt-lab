# Rewrite CONTEXT.md in the vocabulary the tool actually uses

Type: task
Status: open

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
