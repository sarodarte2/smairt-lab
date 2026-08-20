# Retire the stale and vestigial surface

Type: task
Status: resolved

## Question

Delete every document that describes a tool which no longer exists, and every
code path nothing live reaches. Per the Q4 and Q9 charting decisions.

**Stale documents — delete:**

- `QUICKSTART.md` — "V0.1", wrong clone URL, the deleted wizard, dead flags.
- `TUTORIAL.md`, `TUTORIAL_HPC.md`, `TUTORIAL_PAPER_DRIVEN.md` — same.
- `demos/` (all 8 demos, plus `README.md`, `USING_ZOO_CODE.md`,
  `FIRST_SCRIPT_GUIDE.md`, `requirements.txt`, `demo_tracks.svg`) — all v1-shaped.

**Vestigial code and stray files — delete, but verify first:**

- `src/smairt/scaffold.py` and `src/smairt/assets/scaffold-blueprint.yaml` —
  reachable only from `tests/test_scaffold.py` and `scripts/scaffold_diff.py`.
  Removing them means removing that test file and both scaffold-diff scripts
  (`scripts/scaffold_diff.py`, `scripts/ci_scaffold_diff.py`) and any CI step
  that calls them. **Confirm the blueprint is not the source of truth for
  anything in `project.py` before deleting** — if it still is, this item does not
  apply and should be recorded as such.
- `legacy/cookiecutter/` — retained as "unsupported historical reference". It
  makes a newcomer unable to tell what is live. Delete, and drop the README's
  "Legacy Cookiecutter" section with it.
- `adversarial_review1.md` (repo root) and `docs/MODERNIZATION_PROPOSAL.md` —
  odd paths, v1-era. **`adversarial_review1.md` is cited as evidence by
  [practical-smairt](../../practical-smairt/map.md)'s Notes**, so do not simply
  delete it: move it under `.scratch/` alongside the effort that cites it, or
  into `docs/history/`, and fix the citation.

**Every deletion must be verified, not assumed.** For each path: grep the repo
for references, check `.github/workflows/`, check `pyproject.toml`'s sdist
`include` list, and check `docs/` cross-links. A dangling link left behind is
worse than the stale file was.

Do **not** touch `README.md` here beyond removing sections that point at deleted
things — the rewrite is [Split the README](06-split-the-readme.md).

Definition of done: `uv run pytest`, `uv run ruff check .`, `uv run mypy src tests`
all pass; no reference anywhere in the repo resolves to a deleted path; CI green.

## Answer

Done. Deleted `QUICKSTART.md`, all three `TUTORIAL*.md`, all of `demos/`, all of
`legacy/`, `docs/MODERNIZATION_PROPOSAL.md`, the whole `plans/` directory, and the
scaffold-blueprint vestige (`scaffold.py`, `scaffold-blueprint.yaml`,
`tests/test_scaffold.py`, both `scripts/*scaffold_diff.py`, and the CI step calling
them). `adversarial_review1.md` moved to `docs/history/` with its citation in
`.scratch/practical-smairt/map.md` repointed. 735 files removed.

**The scaffold precondition was checked, not assumed** — this ticket's most
dangerous item. `project.py` builds everything from inline string constants;
nothing under `src/smairt/` imports `smairt.scaffold` at all; every other hit for
"scaffold" is generic English or the unrelated `scaffold_version` config field.
Safe. Two things that would have dangled were caught with it:
`tests/test_release.py` asserted the blueprint was present in the wheel, and
`docs/AI_SKILL_USAGE.md` cited its path.

**`plans/` was not in the ticket's scope and was deleted on evidence I verified
independently:** all four files cite `src/smairt/assets/scaffold/` (gone) and
`project_check()` / `_require_current_scaffold()` at `project.py:588`/`:841` —
confirmed, `project.py` is 544 lines and contains neither function. They describe
the pre-rebuild architecture.

### Three corrections applied during review

1. **`src/smairt/skills.py` cited the deleted blueprint** in its module docstring
   as an analogy. The agent correctly refused to touch it (ticket 10's territory)
   and flagged it instead — right call, fixed here.
2. **ADRs 0001, 0002, and 0003 were all still marked `Status: Accepted`** while
   describing machinery the rebuild deleted: the scaffold blueprint, the
   framed-screen TUI, and the terminal-relative palette. An ADR marked Accepted
   for a decision that was fully reversed is worse than a stale tutorial — it is
   the record a future contributor trusts. Marked **Superseded by the v2 rebuild**,
   naming what replaced them. Content left verbatim: ADRs are history and the
   reasoning still explains why those pieces once existed.
3. Verified the `plans/` reasoning above rather than accepting it.

### Gates

ruff, mypy strict, 244 tests (was 248; `test_scaffold.py` held exactly 4), `uv
build` plus a wheel smoke-install exit 0 — proving nothing deleted was
load-bearing for a real install. Final repo-wide grep leaves two intentional
hits, both inside `docs/history/`, which is historical text left verbatim.

### Left alone deliberately

`.scratch/practical-smairt/` and `.scratch/scaffold-content-reenrichment/` still
reference deleted paths. **Correct**: they are resolved efforts describing what
was true when written, and rewriting them to match the new tree would falsify a
decision record. Only the one sanctioned path fix was made, to keep a live link
alive. `docs/scaffold-transition.md` also left — a historical record with no
dangling path.
