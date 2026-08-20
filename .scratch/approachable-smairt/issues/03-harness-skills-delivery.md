# Where each harness loads skills from

Type: research
Status: resolved

## Question

The map decided (Q5) that `smairt connect` will install SMAIRT's skills into each
harness's own skills surface, alongside the hooks it already writes. That
decision needs facts before it can be implemented.

For each of the six harnesses SMAIRT already supports — `claude-code`, `codex`,
`cursor`, `opencode`, `gemini-cli`, `pi` — establish, from primary sources
(official documentation, not blog posts or recollection):

1. **Does it have a project-local, agent-invocable procedure surface at all?**
   (Claude Code skills, Cursor rules, OpenCode/pi plugins, etc.) Name it.
2. **Exact path**, project-local, that `smairt connect` would write to.
3. **File format and required metadata** — e.g. a `SKILL.md` with YAML
   frontmatter naming `name` and `description`, or something else entirely.
4. **Invocation model** — does the agent discover it automatically, does the user
   invoke it by name, or must it be registered somewhere?
5. **Whether project-local files are trusted by default** or require an explicit
   user opt-in (Codex's hooks already need trusting — does the same apply here?).
6. **Multi-file support** — can one procedure ship supporting files, or must it be
   a single file?

Where a harness has **no** such surface, say so plainly and record what the
nearest substitute is (an always-applied rules file, an `AGENTS.md` appendix, or
nothing) — a null result is a real finding here, and the implementation must
degrade gracefully for those harnesses rather than pretend.

Cross-check against the existing precedent in this repo:
`.scratch/practical-smairt/research/10-harness-guidance-conventions.md` surveyed
these same harnesses for *hooks and instruction files* and is the model for
depth and format. Note where anything in it has since changed.

Output a per-harness table plus a short recommendation on how
`_HARNESS_HANDLERS` in `src/smairt/connect.py` should be extended.

## Answer

Full findings: [research/03-harness-skills-delivery.md](../research/03-harness-skills-delivery.md).

**All six harnesses have a project-local skills surface — no null results.**
`.agents/skills/<name>/SKILL.md` reaches five of six; Claude Code is the sole
exception and needs `.claude/skills/<name>/SKILL.md`. Recommended dispatch is
therefore two paths, not six, via one `_install_skills()` helper plus one line
per `_connect_*`. `connect.py`'s existing byte-compare idempotency makes the
shared `.agents/` target free — the second harness connected reports `skipped`.

**Copy, not reference — decisively.** Reference is not *expressible* in four of
six harnesses: Claude Code, Cursor, OpenCode, and Codex have no project-local
"also read skills from here" key (Claude Code's `--add-dir` is a launch flag, not
committed config; Codex's `[[skills.config]]` disables skills rather than adding
search roots). A reference would also resolve to a per-venv `site-packages` path
that breaks for the second person who clones the project. Copies are 8 files /
11.7 KB, committed, readable, and deletable — the same properties everything else
`connect.py` writes already has. Drift is the accepted cost; mitigate with a
provenance line in each generated `SKILL.md` naming the "delete and re-run"
remedy.

**Blocking prerequisite discovered — not in any documentation.** `skills/` lives
at the repo root and is in neither the wheel (`packages = ["src/smairt"]`) nor the
sdist `include` list. **Verified independently against `pyproject.toml`.** A
pip- or uv-installed `smairt connect` cannot reach the skill bytes at all. They
must move under `src/smairt/assets/` before delivery can work at all. Split out
as [ticket 11](11-ship-the-skills-in-the-package.md), which now blocks
[ticket 09](09-deliver-skills-through-connect.md).

**Correction to prior work.** `.scratch/practical-smairt/research/10-harness-guidance-conventions.md`
records that skills are "not portable / Claude Code only". That is now flatly
wrong — the `.agents/skills/` convention post-dates it. Noted, not edited: it is
a resolved record of a reached map.

**Five facts could not be verified from primary sources.** The one that matters:
Codex repo-local skill injection is contradicted by OpenAI's own tracker
([codex#16012](https://github.com/openai/codex/issues/16012), "Repo-local
.agents/skills skill is not injected into session"). **Smoke-test the Codex path
by hand before trusting it** — ticket 09 carries this. The others (Claude Code's
undocumented `.agents/` support, OpenCode's default `permission.skill`, OpenCode
multi-file skills, whether Gemini CLI's frontmatter is validator-enforced) do not
change the recommendation.

**Settles a map open question:** `docs/AI_SKILL_USAGE.md` exists solely to work
around the gap `connect` will close, and becomes wrong-or-redundant on
implementation. Removed from Not yet specified; folded into ticket 09.

### Verification pass (Context7, primary sources)

Re-checked against indexed primary docs and source. Three of five unverified
items resolved; the recommendation is unchanged and now better grounded.

- **Codex confirmed at source level** — `codex-rs/core-skills/src/loader.rs`
  implements `.agents/skills/` repo discovery. No feature flag; the trust prompt
  does not name skills among what trust enables. codex#16012 is most likely a
  bug, not a gap. The ticket-09 smoke-test stays, downgraded to a sanity check.
- **Claude Code's `.agents/` gap confirmed by enumeration** — official docs list
  the skill locations and `.agents/skills/` is not among them. The two-path
  dispatch is the right design.
- **OpenCode confirmed native** (no plugin needed) with all six search locations;
  `permission.skill` takes per-skill globs, not a scalar. Its default value is
  still unstated — remains unverified.
- **New, unsought finding:** Claude Code's `disable-model-invocation: true` and
  Codex's `agents/openai.yaml` invocation policy both enforce
  researcher-invoked-only. `smairt-adversarial-review` currently asserts this in
  prose with nothing behind it. Folded into ticket 09.
