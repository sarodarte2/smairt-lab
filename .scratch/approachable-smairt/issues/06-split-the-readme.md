# Split the README

Type: task
Status: resolved
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

## Answer

Split. `README.md` is now 237 lines and carries the path in — what SMAIRT is,
install, create a project, the shape you get, the loop you work in, connecting an
assistant, Git, data, where to go next. `docs/REFERENCE.md` (319 lines) carries
the precision — per-command flag tables for all nine commands, the full harness ×
wiring × skills-path matrix, the complete `SMAIRT001`–`SMAIRT010` /
`SMAIRT101`–`SMAIRT105` rule table verbatim from `check.py`, output format,
limits, and the development gates.

Register is professional and explains *why* a convention exists rather than only
stating it — the HARKing rationale for hypothesis-and-plan-before-run is the
clearest case. Every documented flag was verified against the live CLI's `--help`
plus `cli.py`, which is the check the deleted tutorials never had. The README
states plainly that there is no worked example and why, rather than implying one.

### One real error, caught on review

The README claimed **"a question's `hypothesis:` must hold real text before it
can be created."** It must not — and this matters, because it is exactly the
distinction ticket 02 settled. `--hypothesis` is deliberately an optional flag so
a researcher can create the unit and write the claim in their editor; `SMAIRT009`
makes an *empty* hypothesis a check error, not a creation error. Making the flag
mandatory would only train people to type `--hypothesis "tbd"`.

Verified empirically before fixing: `smairt unit new question --title "..."` with
no `--hypothesis` succeeds. Corrected to say both fields must be non-empty before
the question can close, and that neither is a flag you are forced to pass up
front.

### The agent's out-of-scope find, corrected

It reported that `docs/ARCHITECTURE.md` said `smairt check` has "eleven rules"
and refused to fix it, being outside this ticket. It was right that the number
was wrong — but so was its proposed replacement. Counted directly: **10 `_check_*`
functions, 4 `_suggest_*` functions, 10 finding ids, 5 suggestion ids.** The
"eleven" came from ticket 10 bumping a pre-existing "eight" that had grouped all
growth suggestions as a single rule. Replaced the bare count with the precise
statement — ten finding rules, five advisory — matching `check.py`'s docstring
and `CONTEXT.md`, so there is no single number left to drift.

All cross-links verified to resolve; 244 tests unaffected.
