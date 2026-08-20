# ADR 0004: Deliver SMAIRT's Skills by Copying Them Into Two Harness-Local Paths

Status: Accepted

## Context

SMAIRT ships eight `smairt-*` skills — thin, assistant-facing procedures such
as "run `smairt status` first, always" or "the interview is the wizard" — as
package data under `src/smairt/assets/skills/`. Nothing put them in front of
an assistant. `docs/AI_SKILL_USAGE.md` said only "make `skills/` available to
an assistant," which is undefined, manual, and reliably skipped. Under this
project's audience floor, where the assistant is the daily surface, every
procedure silently failing to arrive was the largest functional gap in the
tool.

A survey of all six supported harnesses (`.scratch/approachable-smairt/research/03-harness-skills-delivery.md`,
verified against each vendor's own documentation and, for the doubtful cases,
Context7 and source-level reads of `codex-rs`) found that every one of them
has converged on the same open standard: a directory per skill holding a
`SKILL.md` with YAML frontmatter (agentskills.io). The project-local path is
`.agents/skills/<name>/SKILL.md` for five of six — Codex's *only* repo path,
Gemini CLI's higher-precedence alias, and a documented location for Cursor,
OpenCode, and pi. Claude Code is the one exception: its own docs enumerate
skill locations and `.agents/skills/` is not among them, so it needs
`.claude/skills/<name>/SKILL.md`.

Two questions the survey could not settle by reading docs alone had to be
decided: copy the skill text into the project, or reference it in place; and
whether the one skill that says "researcher-invoked only" in prose
(`smairt-adversarial-review`) should get an actual mechanism behind that
claim.

## Decision

`smairt connect <harness>` installs all eight skills into that harness's
project-local skills surface, alongside the hooks it already writes — same
command, same per-harness dispatch table (`_HARNESS_HANDLERS` in
`connect.py`), same never-overwrite-a-researcher's-edit policy every other
generated file already honors. The dispatch collapses to two targets, not
six: `.claude/skills/` for Claude Code, `.agents/skills/` for the other five.
Connecting a second harness that shares `.agents/skills/` with an
already-connected one is a free no-op — the existing byte-compare idempotency
finds identical files and reports them `skipped`.

Skills are **copied**, not referenced. No harness has a project-local "also
read skills from this other path" setting — Codex's `[[skills.config]]`
*disables* named skills rather than adding a search root, and Claude Code,
Cursor, and OpenCode have no equivalent key at all. A reference would only be
expressible in two of six harnesses, and even there it would resolve to a
per-venv `site-packages` path that breaks the moment a second person clones
the project. Copies drift on a `smairt` upgrade instead; that cost is
accepted and mitigated with a provenance comment in every installed
`SKILL.md` naming the "delete this directory and re-run `smairt connect`"
remedy — inserted after the closing frontmatter delimiter, never before it,
since Cursor and OpenCode only recognize frontmatter that opens on a file's
first line.

`smairt-adversarial-review`'s "researcher-invoked only — never run this
unprompted" claim gets a real mechanism wherever one genuinely exists:
`disable-model-invocation: true` in the frontmatter, honored by Claude Code,
Cursor, and pi, and harmlessly ignored by the rest. The other seven skills stay
model-invocable with the plain two-field frontmatter every harness accepts
unmodified — automatic firing is the point of `smairt-orient` and the rest.

The Codex path was smoke-tested against a real, installed Codex CLI
(`codex-cli 0.146.0`), not just source-read, because a vendor tracker issue
(openai/codex#16012) reports repo-local `.agents/skills` failing to load.
Repo-local discovery itself worked: a skill dropped into `.agents/skills/`
appeared in Codex's injected `<skills_instructions>` block by name and file
path, so openai/codex#16012 does not reproduce here.

Codex's `agents/openai.yaml` policy file — the documented counterpart to
`disable-model-invocation` — is deliberately **not** written. Measured against
`codex-cli 0.146.0` it does not behave as documented: instead of suppressing
automatic selection while leaving explicit `$skill` invocation available, it
removes the skill from the injected list entirely. Isolated by bisection — an
`agents/openai.yaml` carrying only an `interface:` block leaves the skill
visible; adding `policy:`, alone or alongside `interface:`, is what makes it
vanish. Since `smairt-adversarial-review` has no mode of use except explicit
researcher invocation, that file would not constrain the skill on Codex, it
would delete it — trading a working anti-bias mechanism for none at all. Codex
therefore falls back to the SKILL.md prose, exactly as Gemini CLI and OpenCode
already do. Revisit if a future Codex release makes the documented behavior
real.

## Consequences

- A researcher who runs `smairt connect <harness>` for any of the six
  supported harnesses now gets SMAIRT's procedures in front of that
  assistant automatically — closing the gap `docs/AI_SKILL_USAGE.md`
  previously described as a manual, undefined step.
- Installed skills are ordinary project files: committed, readable, and
  deletable, with the same properties as every other file `connect.py`
  writes. Deleting a skill's directory disables it; deleting and re-running
  `smairt connect <harness>` refreshes it to the version the installed
  `smairt` currently ships.
- A project connected to several harnesses that share `.agents/skills/`
  stores exactly one copy of each skill, not one per harness.
- Skills will drift from the shipped version across a `smairt` upgrade until
  a researcher re-runs `connect`; there is no automatic upgrade path, by the
  same logic that already governs hook-config drift in `connect.py` (a
  present-but-different file is assumed researcher-edited and is never
  silently rewritten).
- On Codex, Gemini CLI, and OpenCode, `smairt-adversarial-review`'s
  researcher-invoked-only rule remains prose with nothing enforcing it — the
  same honor system as before this change, and no worse. It is enforced on
  Claude Code, Cursor, and pi.
- Adding a seventh harness means adding one `_install_skills(...)` call to
  its `_connect_<name>` function, choosing whichever of the two existing
  targets that harness's own docs name — not inventing a third path.
