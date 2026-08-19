# Survey: harness guidance conventions

Type: research
Status: resolved

## Question

What do the major AI coding harnesses (Claude Code, OpenAI Codex CLI, OpenCode, Gemini CLI, Cursor) actually read from a repository — AGENTS.md standard, CLAUDE.md, rules files, skills — per their primary documentation? Which guidance mechanisms are portable across harnesses, which are harness-specific, and which support any form of enforcement (hooks, checks) rather than mere suggestion?

Findings: `.scratch/practical-smairt/research/10-harness-guidance-conventions.md`

## Answer

Full findings, with every claim cited to primary documentation, in `.scratch/practical-smairt/research/10-harness-guidance-conventions.md`. Conclusions:

1. **AGENTS.md has the widest reach.** Native in OpenAI Codex (its originating convention; global `~/.codex/AGENTS.md` plus git-root-down concatenation, 32 KiB cap), OpenCode (primary rules file, CLAUDE.md as compat fallback), and Cursor (root + nested). Gemini CLI reads it via a one-line `context.fileName` setting. Claude Code is the sole holdout — its docs state it reads CLAUDE.md, not AGENTS.md — but the same docs prescribe the bridge: a CLAUDE.md containing `@AGENTS.md` or a symlink.
2. **Instruction files are advisory in every harness** (Claude Code's docs say so explicitly). Enforcement is a separate layer, and all five harnesses now expose a blocking pre-tool-use hook: Claude Code `PreToolUse`, Codex `PreToolUse` in `.codex/hooks.json`, Gemini CLI `BeforeTool`, Cursor `preToolUse`/`beforeShellExecution`, OpenCode `tool.execute.before`. Each also has its own permission/sandbox layer.
3. **Implication for SMAIRT:** one canonical repo-root `AGENTS.md` for prose reaches every harness with near-zero duplication (2-line CLAUDE.md import, one Gemini setting), and a single `smairt check`-style CLI can be wired into each harness's blocking hook — with CI as the only enforcement floor that binds regardless of local hook config. Only hook wiring is harness-specific; guidance and check logic are written once.
