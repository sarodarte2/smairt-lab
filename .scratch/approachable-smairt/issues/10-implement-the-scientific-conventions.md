# Implement the scientific conventions

Type: task
Status: open
Blocked by: 01, 02

## Question

Implement whatever [The sidequest and unit lineage](01-sidequest-lineage.md) and
[The pre-specified analysis plan](02-pre-specified-analysis-plan.md) decided.

They are one ticket rather than two because they land in the same files and would
otherwise conflict: `src/smairt/units.py` (frontmatter schemas and the creator
functions), `src/smairt/check.py` (new rules), `src/smairt/project.py`
(`_AGENTS_TEMPLATE`), and the golden fixture.

Whatever the shape turns out to be, this ticket carries the full blast radius —
it is easy to add a field and miss half the places that must agree:

- `units.py`: `STAGE_REQUIRED_FIELDS` / `QUESTION_REQUIRED_FIELDS`, the allowed
  status values, the creator functions, and any new CLI flag on
  `smairt unit new`.
- `check.py`: new rule constants with **new, never-reused `SMAIRTNNN` ids**
  (existing ids are stable contract and must not be renumbered), the rule
  functions themselves, their registration in `run_checks()`, and the module
  docstring's ID table — which is the tool's actual rule documentation.
- `project.py`: `_AGENTS_TEMPLATE`, so the contract every assistant reads
  states the new convention. Keep the file under ~120 lines as its own footer
  demands — if the new conventions do not fit, that is a signal about their
  weight, not a licence to grow the file.
- The relevant `skills/smairt-*/SKILL.md` — at minimum `smairt-new-question` and
  `smairt-close-question`, which walk the exact moments these conventions govern.
- `tests/fixtures/golden/` — regenerate, and confirm it still passes
  `smairt check` clean.
- `docs/ARCHITECTURE.md` — the "Adding things" section describes how a rule is
  added; make sure what actually landed matches it.
- `CONTEXT.md` — the terms should already be there from 01 and 02 resolving
  (per domain-modeling); verify, don't assume.

Requirement carried from the map's Notes: **supervisable**. A new check rule that
fires on work a researcher believes is correct, without saying plainly what to do
about it, trains them to ignore `smairt check` — which is how the previous
iteration's conventions decayed. Each new rule's message must name the fix.

Definition of done: `uv run pytest`, `uv run ruff check .`,
`uv run mypy src tests` green; a freshly created project still passes
`smairt check` with zero findings (the WP1 acceptance criterion); the README /
`docs/REFERENCE.md` describe the new conventions.
