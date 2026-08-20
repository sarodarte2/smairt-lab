# Ship the skills inside the package

Type: task
Status: resolved

## Question

`skills/smairt-*` sits at the repository root and is packaged by nothing:
`pyproject.toml` declares `packages = ["src/smairt"]` for the wheel, and the sdist
`include` list names `/src/smairt`, `/tests`, `/scripts/smoke_install.py`,
`/README.md`, `/LICENSE` — no `/skills`. Verified directly against
`pyproject.toml`.

Consequence: an installed `smairt` (the only supported install path, per the
README) has no access to the skill files at all. Every delivery mechanism
[ticket 09](09-deliver-skills-through-connect.md) could build is dead on arrival
until this is fixed. Discovered while resolving
[ticket 03](03-harness-skills-delivery.md).

Move the skills under `src/smairt/assets/skills/` so they ship as package data,
alongside the existing `src/smairt/assets/` precedent.

Requirements:

- Skills must be readable from an **installed** package, not just a source
  checkout — resolve them via `importlib.resources`, never a path relative to
  `__file__`'s parent directories.
- Verify against a real install, not just the source tree:
  `scripts/smoke_install.py` already installs the built wheel and sdist into a
  throwaway workspace and is the right place to assert the skills are present.
- Update every reference to the old `skills/` path: `docs/AI_SKILL_USAGE.md`,
  `README.md`, `src/smairt/adopt.py`'s module docstring (cites
  `skills/smairt-adopt/SKILL.md`), and any cross-links in `docs/`.
- Confirm the wheel actually contains them (`unzip -l dist/*.whl | grep skills`)
  rather than trusting the config change.

Definition of done: a wheel built from a clean tree contains all eight skills;
the smoke-install script asserts it; `uv run pytest`, `uv run ruff check .`,
`uv run mypy src tests` green.

## Answer

Implemented. All eight skills moved to `src/smairt/assets/skills/` via `git mv`
(history preserved), with `src/smairt/skills.py` as the single lookup point —
`list_skills()` / `read_skill()` resolving through `importlib.resources`, never a
path built from `__file__`. `tests/test_skills.py` covers both plus the unknown
-name case; `scripts/smoke_install.py` now asserts the skills are readable *from
the installed venv*, which has never seen the source tree.

Verified independently by the main session, not taken on report: ruff format,
ruff check, mypy (strict), 214 tests, `uv build`, **8 skills present in both
`dist/*.whl` and `dist/*.tar.gz`**, both smoke-installs exit 0, and a repo-wide
grep finds no surviving reference to the old `skills/` path.

**Two things this ticket got wrong, corrected:**

1. **`pyproject.toml` needed no change at all.** The ticket named the wheel's
   `packages = ["src/smairt"]` and the sdist `include` list as the thing to fix.
   In fact hatchling already ships every tracked, non-ignored file under
   `src/smairt` — which is why `assets/scaffold-blueprint.yaml` was shipping with
   no explicit config. The root-cause diagnosis was right (the *old location* was
   outside the packaged tree); the prescribed fix was wrong. **The `git mv` alone
   is the entire fix.** Confirmed empirically by building before touching
   `pyproject.toml`.
2. **`README.md` never referenced `skills/`.** Listed as a known reference to
   update; a case-insensitive grep finds zero hits in the current tree.

`.github/workflows/ci.yml` also needed no edit — it never named the old path and
already runs `smoke_install.py` against both artifacts, so the new assertion is
enforced in CI for free.

**Small follow-up, not blocking:** the expected skill count is hardcoded in two
places (`_EXPECTED_SKILLS` in the test, `== 8` in `smoke_install.py`). That is a
deliberate tripwire, but a legitimate ninth skill will fail the release gate
until both are bumped. Worth collapsing to one source if a skill is ever added.
