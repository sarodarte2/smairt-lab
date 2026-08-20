# Deliver the skills through `smairt connect`

Type: task
Status: open
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
