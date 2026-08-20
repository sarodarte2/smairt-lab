# Deliver the skills through `smairt connect`

Type: task
Status: resolved
Blocked by: 03, 11

## Question

Implement the Q5 charting decision: `smairt connect <harness>` installs SMAIRT's
skills into that harness's own procedure surface, alongside the hooks it already
writes.

The gap being closed: nothing currently puts `skills/smairt-*` in front of any
assistant. `docs/AI_SKILL_USAGE.md` says only "make `skills/` available to an
assistant" — undefined, manual, and reliably skipped. Every procedure SMAIRT
ships (`smairt-new-project`'s "the interview is the wizard",
`smairt-orient`'s "run `smairt status` first, always",
`smairt-close-question`'s facts-before-interpretation discipline) silently fails
to arrive. Under this map's audience floor, where the assistant *is* the daily
surface, that is the single largest functional gap in the tool.

Implement from [ticket 03](03-harness-skills-delivery.md)'s per-harness findings.

Requirements:

- Follow the existing shape in `src/smairt/connect.py`: one render/connect
  function per harness, dispatched through `_HARNESS_HANDLERS`. Do not invent a
  parallel mechanism.
- Honor the policies `connect` already guarantees and the README already
  promises: every generated file names itself as generated; re-running never
  overwrites a file the researcher edited (report "unchanged" if identical, warn
  and leave alone if it differs); everything written is project-scoped and can
  never leak into a global config; deleting the file disables the wiring.
- **Degrade honestly.** Harnesses with no skills surface must say so plainly
  rather than writing a file that does nothing.
- Decide and record: are skills **copied** into the project (self-contained,
  goes stale on upgrade) or **referenced** in place (always current, breaks if
  the checkout moves)? 03's format findings may force this. If copied, the
  scaffold-version mismatch machinery may need to cover them.
- **Enforce researcher-invoked-only where the harness supports it.**
  `smairt-adversarial-review` says "Researcher-invoked only — never run this
  unprompted" as prose with no mechanism behind it. Claude Code has
  `disable-model-invocation: true` (SKILL.md frontmatter); Codex has an optional
  `agents/openai.yaml` carrying invocation policy — SMAIRT shipped files at that
  exact path in v1 and deleted them in the rebuild. Decide which SMAIRT skills
  are model-invocable and which are not, and express it per harness.
- **Smoke-test the Codex path by hand** before shipping it. Source-level
  verification confirms `.agents/skills/` discovery is implemented
  (`codex-rs/core-skills/src/loader.rs`), so this is a sanity check, not a
  go/no-go gate — but [codex#16012](https://github.com/openai/codex/issues/16012)
  reported it not working, so confirm empirically rather than trusting the read.
- Tests in `tests/test_connect.py` for each harness, following the existing
  per-harness test shape.
- Update `docs/AI_SKILL_USAGE.md` — most of it exists to work around this gap,
  so much of it should now be deleted rather than revised.

This decision is hard to reverse (it sets a contract with six external tools),
surprising without context, and the result of a real trade-off. **Offer an ADR
under `docs/adr/` when it lands.**

## Answer

Implemented. `smairt connect <harness>` now installs all eight skills through a
single `_install_skills()` helper on the existing `_HARNESS_HANDLERS` dispatch —
`.claude/skills/<name>/SKILL.md` for Claude Code, `.agents/skills/<name>/SKILL.md`
for the other five. Copied, never referenced; read only through `smairt.skills`.
ADR recorded at `docs/adr/0004-copy-skills-into-two-harness-local-paths.md`.

The provenance notice is inserted *after* the closing frontmatter delimiter and
deliberately never names a specific harness under the shared root — naming one
would make the rendered bytes depend on which harness wrote first, destroying the
free cross-harness idempotency.

**Verified by the main session against a real throwaway project, not taken on
report:** ruff, mypy (strict), 227 tests; `connect claude-code` → 8 files under
`.claude/skills/`; `connect codex` → 8 under `.agents/skills/`; `connect cursor`
→ all 8 shared files reported `Unchanged`; hand-editing a SKILL.md and re-running
leaves it untouched with a warning, edit preserved.

### Codex's policy file: found broken, and NOT shipped

The agent's Codex smoke test was correct and I reproduced it independently
against `codex-cli 0.146.0` using `codex debug prompt-input`:

| Setup | Codex sees the skill? |
|---|---|
| bare `.agents/skills/<n>/SKILL.md` | **yes** — codex#16012 does not reproduce |
| `+ agents/openai.yaml` with `policy: allow_implicit_invocation: false` | **no — vanishes entirely** |
| `+ agents/openai.yaml` with `interface:` only | **yes** |

The agent shipped the policy block anyway, reasoning it still achieves the safety
property. **Reversed on review, with the user's decision.** `smairt-adversarial-review`
has no mode of use except explicit researcher invocation, so on Codex that file
does not constrain the skill — it deletes it, trading a working anti-bias
mechanism for none at all. Codex now falls back to the SKILL.md prose exactly as
Gemini CLI and OpenCode do.

The generated file also asserted "explicit `$` invocation is documented to still
work", which the smoke test had already disproved — a generated file stating
something false, against this project's own bar. Removed with the mechanism.

**Net enforcement:** `disable-model-invocation: true` is real on Claude Code,
Cursor, and pi. On Codex, Gemini CLI, and OpenCode the rule stays prose — the
same honor system as before, and no worse.

### Left incomplete, honestly

Per-harness informational caveats from the research (pi's trust prompt, Codex's
restart-required note, OpenCode's no-slash-command note) were **not** surfaced in
`connect` output: `ConnectResult` has no generic-notice channel and adding one is
beyond this ticket. Worth a follow-up — a researcher on pi can have every file
written correctly and still see no skills, because the trust prompt was never
answered.
