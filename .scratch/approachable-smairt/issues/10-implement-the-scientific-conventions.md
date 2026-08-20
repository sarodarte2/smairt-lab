# Implement the scientific conventions

Type: task
Status: resolved
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

## Answer

Implemented. Three new check rules (`SMAIRT008` dangling `prompted_by:`,
`SMAIRT009` empty `hypothesis:`, `SMAIRT010` empty `## Analysis plan` on a closed
question), a `--from` flag validated at creation, `## Analysis plan` in the
question body template, `INDEX.md` nesting, updated `_AGENTS_TEMPLATE` and both
question skills, regenerated golden fixture, and ADR 0005. 248 tests; ruff, mypy
strict, and pytest all clean.

**Verified by the main session against a throwaway project**, not taken on report:
three-level `--from` nesting renders correctly; a dangling `--from` fails at
creation naming the fix; `SMAIRT009` and `SMAIRT010` both fire on a closed
question and clear once filled; a fresh project still passes with zero findings.

### Two corrections applied during review

1. **`INDEX.md` used `&nbsp;` HTML entities for indentation.** They render on
   GitHub but a scientist reading `INDEX.md` in a terminal or editor sees literal
   `&nbsp;&nbsp;↳ Title`. Replaced with a real U+00A0 non-breaking space, which
   survives Markdown whitespace-collapsing *and* looks like indentation in plain
   text — the point of keeping these records as readable files.
2. **`AGENTS.md` never mentioned `prompted_by:` or `--from`.** The spec listed
   three additions and all three landed, but `check` deliberately never nags for
   the link and `AGENTS.md` is the only file every assistant always reads — so
   the feature was invisible outside one skill. Added the mechanism and the
   hypothesis-test boundary to the Units section. Template is 97 lines, still
   under its own ~120 cap.

### The agent's own judgment call, accepted

`SMAIRT009` and `SMAIRT010` both exempt **reference units** (`paths:` present).
Ticket 02 stated this only for the plan rule; without the same exemption on the
hypothesis rule, every unit created by `smairt unit new question --ref ...` —
i.e. everything `smairt adopt` produces — would permanently fail check. Correct
call, documented in `check.py`'s "Judgment calls" section.

`SMAIRT009` fires on **any** status, not just closed. This is right and is the
stricter default: waiting until close to demand the claim would let the claim be
written after the result is known, which is the exact retrofitting
hypothesis-before-run exists to prevent. It did break several previously-passing
tests that created questions without `--hypothesis`; those were fixed, not
weakened.
