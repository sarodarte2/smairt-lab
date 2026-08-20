# Retire the stale and vestigial surface

Type: task
Status: open

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
