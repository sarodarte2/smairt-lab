# Split the README

Type: task
Status: open
Blocked by: 01, 02

## Question

Per the Q7 charting decision: split `README.md` into a short, approachable
`README.md` and a `docs/REFERENCE.md`.

The current README (12.6KB) is accurate and v2-current — this is not a
correctness fix. It is two documents wearing one coat: the first third is a story
(what SMAIRT is, how to install it, how to make a project), the rest is reference
material (the full command table, the harness wiring matrix, the check output
format, the development gates). Those two jobs pull the register in opposite
directions, and the reference half is why the whole thing reads formal.

It also just inherited every job the deleted documents had — with
`QUICKSTART.md`, the tutorials, and the demos gone, this is the only path in.

**`README.md` — the path in.** What SMAIRT is and the problem it solves, install,
create a project, the shape you get, the loop you work in, where to go next.
Written for the map's floor audience: a scientist who can run a command and read
Python but may not write it. **Professional, not casual** — approachable means
"assumes no jargon and explains why," not jokes.

**`docs/REFERENCE.md` — the precision.** The complete command table, the harness
wiring matrix, `smairt check`'s rule IDs and output format, flag-by-flag detail,
the development and release gates. Terse and exact is correct here.

Constraints:

- Every fact must survive the split. The current README's precision is
  load-bearing — nothing gets sanded off in the name of tone.
- Fix the "Legacy Cookiecutter" section and anything else pointing at paths
  [ticket 04](04-retire-the-stale-surface.md) deleted.
- The README must not promise a worked example or tutorial — there isn't one, and
  that is a recorded, deliberate gap (see the map's Out of scope).

**Blocked by [01](01-sidequest-lineage.md) and [02](02-pre-specified-analysis-plan.md):**
both change the conventions a researcher works in, and the README documents those
conventions. Writing it before they land means writing it twice.
