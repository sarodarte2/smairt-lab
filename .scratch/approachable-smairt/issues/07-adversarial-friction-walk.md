# Adversarial friction walk

Type: task
Status: resolved

## Question

Per the Q8 charting decision: before writing a single edge-case test, drive the
real CLI as a hostile newcomer and record what actually breaks. Tests written
from imagination cover what was already imagined; the failures that killed the
last iteration were the unmodeled ones.

This ticket produces **facts, not fixes**. Fixes are
[ticket 08](08-fix-the-friction.md).

Install the tool cleanly into a throwaway workspace (`uv tool install .`, not
`uv run`, so the installed entry point is what gets exercised), then work every
command with intent to break it. At minimum:

**Identity and naming** — a name that slugifies to nothing (`"???"`, emoji-only,
pure punctuation); a name with Unicode, accents, or CJK; a name colliding with an
existing directory; an extremely long name; a name with path separators or `..`.

**`smairt new`** — an existing non-empty target; a target inside an existing
SMAIRT project; a read-only parent; a relative vs. absolute `--path`; every
`--harness` value including `none` and an invalid one; the non-interactive path
with flags missing; piped stdin; `--no-git` inside a repo and `--git` outside one.

**`smairt adopt`** — a directory that is already a SMAIRT project; an empty
directory; a directory full of unrelated files; one with a top-level folder named
the same as a scaffold folder (`data/`, `experiments/`) that has different
contents; a Git repo with uncommitted changes.

**`smairt unit new`** — duplicate titles on the same day (question collision);
titles differing only in punctuation; creating a stage when `experiments/` has a
hand-made folder with a numeric prefix; `--receipt` with missing `--tool`;
`--ref` pointing at a nonexistent path, at an absolute path, at `..` outside the
project.

**`smairt data`** — `--hpc` with no colon, with an empty half, with a URL in it;
`locate` on a dataset that does not exist; a dataset name colliding after
slugification; `list` with no datasets.

**`smairt check` / `status` / `index`** — run from a deep subdirectory; run
outside any project; run in a project with a corrupt `smairt.yaml`; with malformed
YAML frontmatter in a unit README; with no frontmatter at all; with a unit folder
containing no README; `--json` on every command that offers it, validated as
actual JSON.

**`smairt connect`** — every harness; twice in a row; after hand-editing a
generated file; with `strict_hooks: true`; `--ci`. Then verify the claim the
README makes, that generated wiring is project-scoped and cannot leak globally.

**`smairt hook report|gate`** — outside a project (verify the loud message and
that it exits 1, never 2); with findings present; with none.

For every finding record: **command run, expected, actual, severity**
(crash / wrong result / confusing message / merely rough), and — the point of the
exercise — **whether the floor audience could recover from it unaided**. A
traceback a Python developer shrugs at is a dead end for the reader this map is
written for.

Output the inventory as `.scratch/approachable-smairt/research/07-friction-inventory.md`
and link it from the resolution.

## Answer

Walk complete against an installed `smairt 0.4.0` (`uv tool install --force .`,
not `uv run`). Inventory at
[research/07-friction-inventory.md](../research/07-friction-inventory.md):
**13 findings — 3 crash root causes (5 reproductions), 2 wrong-result defects,
3 confusing messages, 5 design gaps.**

The three worst, all verified independently by the main session:

1. **Malformed YAML inside a well-formed frontmatter block** — an unclosed
   `tags: [`, exactly the mistake a scientist hand-editing a README makes —
   crashed `check`, `status`, and `index` with a raw `yaml.parser.ParserError`.
   `smairt check`'s entire job is reporting frontmatter problems as findings, and
   it crashed on one instead, exiting 1: indistinguishable from a legitimate
   "findings exist" exit.
2. **A README with no frontmatter** crashed `status` and `index` while `check`
   handled the identical file cleanly — three commands disagreeing about one file.
3. **An absolute path in `--ref`/`paths:` passed `check` clean** if it existed
   anywhere on the machine (verified with `/etc/hosts`) — silent wrongness, worse
   than a crash, and a direct violation of the project-root contract.

**Nothing leaked outside the project root.** `$HOME` was diffed before and after
connecting all six harnesses plus `--ci`; the README's project-scoping claim held
under direct test.

**The `prompted_by:` cycle guard works.** A hand-made 6-node cycle did not hang
`index`, verified under a hard timeout — the defensive code written in ticket 10
earned its place on its first real adversarial contact.

The walk also recorded what worked *well* — collision safety, `adopt`'s errors,
Git nesting detection, `--hpc HOST:PATH` validation, `connect` idempotency and
never-clobbering, and the SMAIRT008/009/010 messages — specifically so
[ticket 08](08-fix-the-friction.md) could not fix them away.
