# 10 — What AI coding harnesses actually read from a repository

Research ticket: which files/conventions the major harnesses read for project guidance, whether each has real enforcement (not just advisory text), and whether each honors AGENTS.md — to inform whether SMAIRT should own one canonical machine-readable project contract and derive thin per-harness adapters.

Sources are the vendors' primary documentation (official docs sites or the standard's own site), fetched 2026-08-17. Claims that could not be traced to a primary source are marked **unverified**.

---

## Short answer

1. **AGENTS.md is the convention that reaches the most harnesses today.** OpenAI Codex, OpenCode, Cursor, and (via a one-line config) Gemini CLI read it natively; agents.md lists 25+ supporting tools. The one major holdout is Claude Code, whose docs explicitly say it reads `CLAUDE.md`, not `AGENTS.md` — but the same docs prescribe a one-line bridge (`@AGENTS.md` import or a symlink). So a repo-root `AGENTS.md` plus a two-line `CLAUDE.md` shim covers every harness in this survey.

2. **Instruction files are advisory everywhere.** Every harness loads its guidance file(s) as model context; none treats them as enforced configuration. Claude Code's docs say this outright: "Claude treats them as context, not enforced configuration." Enforcement lives in a different layer in every harness: **hooks** (Claude Code, Cursor, Codex, Gemini CLI, OpenCode plugins — all five now have a pre-tool-use event that can hard-block a tool call) and **permission/sandbox systems** (Claude Code allow/ask/deny rules + sandbox; Codex approval policies + OS-level sandbox; OpenCode allow/ask/deny permissions; Gemini CLI tool allowlists + policy settings; Cursor team rules + hooks).

3. **What is portable vs harness-specific:**
   - *Portable:* prose instructions in a repo-root (and nested, per-directory) `AGENTS.md`; the "closest file wins / concatenate root-down" merge model is shared by Codex, Cursor, Gemini CLI, and Claude Code's own CLAUDE.md walk.
   - *Portable with adapters:* the hook idea — every harness can run an arbitrary shell command before a tool call and block on a nonzero/structured "deny" result, but the config schema, event names, and payloads differ per harness (`.claude/settings.json` hooks, `.cursor/hooks.json`, `.codex/hooks.json`, `.gemini/settings.json` hooks, `.opencode/plugins/*.ts`).
   - *Not portable:* skills (Claude Code / agentskills.io, plus Gemini CLI extensions have a skills template), path-scoped rules (`.claude/rules/` `paths:` frontmatter; `.cursor/rules/*.mdc` globs), permission-rule syntax, sandbox config.

4. **What can actually be enforced:** a deterministic CLI check (e.g. `smairt check`) can be made *blocking* in every harness in this survey via its pre-tool-use hook, and blocking for everyone via CI. Advisory prose can only be communicated.

**Implication for SMAIRT:** the "one canonical machine-readable contract + thin per-harness adapters" architecture matches how the ecosystem is actually shaped. The canonical layer should be (a) one `AGENTS.md` carrying the prose contract (reaches everything, including Claude Code via import), and (b) one CLI check the adapters call. The adapters are small and mechanical: a 2-line `CLAUDE.md` import, a `GEMINI.md` import or `context.fileName` setting, and per-harness hook config files that all invoke the same CLI check. The only content that must be authored per-harness is hook wiring, not guidance.

---

## Per-harness detail

### Claude Code

**Guidance files and when they load** — primary source: [How Claude remembers your project](https://code.claude.com/docs/en/memory)

- **CLAUDE.md** at four scopes, loaded in order broadest→most specific: managed policy (`/Library/Application Support/ClaudeCode/CLAUDE.md` on macOS, `/etc/claude-code/CLAUDE.md` on Linux), user (`~/.claude/CLAUDE.md`), project (`./CLAUDE.md` or `./.claude/CLAUDE.md`), and local (`./CLAUDE.local.md`, gitignored).
- **Load timing:** files in the directory hierarchy at and above the working directory are "loaded in full at launch"; `CLAUDE.md` files in subdirectories "are included when Claude reads files in those subdirectories" (on demand). Discovery walks up the tree; all discovered files are *concatenated*, ordered root-down, so files closer to the working directory are read last.
- **Imports:** `@path/to/file` syntax pulls other files into context at launch, recursively to depth 4. Imports resolving outside the working directory trigger a one-time approval dialog.
- **`.claude/rules/`** — modular rule files; ones without `paths:` frontmatter load at launch, ones with `paths:` globs load only when Claude works with matching files. User-level rules live in `~/.claude/rules/`.
- **Skills** — primary source: [Extend Claude with skills](https://code.claude.com/docs/en/skills). `SKILL.md` files at enterprise / `~/.claude/skills/` / `.claude/skills/` / plugin scopes. Follows the [Agent Skills](https://agentskills.io) open standard. Skill *bodies* load only on invocation or when Claude judges them relevant ("a skill's body loads only when it's used"); nested `.claude/skills/` in subdirectories load when Claude first touches files there.
- **Settings** — primary source: [Configure permissions](https://code.claude.com/docs/en/permissions). `~/.claude/settings.json`, `.claude/settings.json`, `.claude/settings.local.json` (loaded from the git repo root), plus managed policy settings.

**Enforcement** — primary sources: [permissions](https://code.claude.com/docs/en/permissions), [hooks](https://code.claude.com/docs/en/hooks)

- The memory doc is explicit that guidance files are advisory: "Claude treats them as context, not enforced configuration. To block an action regardless of what Claude decides, use a PreToolUse hook instead," and "Settings rules are enforced by the client regardless of what Claude decides to do. CLAUDE.md instructions shape Claude's behavior but are not a hard enforcement layer."
- **Permission rules:** allow/ask/deny with pattern syntax (`Bash(npm run test:*)`, `Read(./secrets/**)`), evaluated deny→ask→allow, first match wins. "Permission rules are enforced by Claude Code, not by the model." Read/Edit deny rules don't cover arbitrary subprocesses; OS-level enforcement requires the [sandbox](https://code.claude.com/docs/en/sandboxing).
- **Hooks:** 30+ lifecycle events; `PreToolUse` can block a tool call via exit code 2 or JSON `permissionDecision: "deny"`; `UserPromptSubmit` can reject prompts; `Stop` can halt. Hook types include command, HTTP, MCP-tool, prompt, and agent hooks. Configured in the settings files above, plugins, or skill/subagent frontmatter. "Hooks execute as shell commands at fixed lifecycle events and apply regardless of what Claude decides to do" ([memory doc](https://code.claude.com/docs/en/memory)).

**AGENTS.md:** *not honored natively.* "Claude Code reads `CLAUDE.md`, not `AGENTS.md`. If your repository already uses `AGENTS.md` for other coding agents, create a `CLAUDE.md` that imports it" (`@AGENTS.md`) or symlink `CLAUDE.md → AGENTS.md` ([memory doc](https://code.claude.com/docs/en/memory#agents-md)). `/init` (with `CLAUDE_CODE_NEW_INIT=1`) and `/import` can also read/convert `AGENTS.md`, Cursor rules, and Copilot rules — one-time copies, not live reads.

### AGENTS.md (the open standard)

Primary source: [agents.md](https://agents.md/)

- **Format/placement:** plain Markdown at the repo root; no required fields or schema — "a simple, open format." For monorepos, nested `AGENTS.md` files go in subproject directories; "the closest AGENTS.md to the edited file wins; explicit user chat prompts override everything."
- **Adoption:** the site lists 25+ supporting agents (OpenAI Codex, Google Jules, Cursor, VS Code/GitHub Copilot, Devin, Aider, Zed, Warp, …). Governance: stewarded by the Agentic AI Foundation under the Linux Foundation (per agents.md).
- **Enforcement:** none. Purely advisory "living documentation." The convention that agents "attempt to execute relevant programmatic checks and fix failures" when commands are listed is an agent-behavior norm, not a mechanism — compliance depends entirely on each implementation.

### OpenAI Codex (CLI)

**Guidance files** — primary source: [Codex docs — AGENTS.md](https://developers.openai.com/codex/guides/agents-md) (the developers.openai.com URLs now 308-redirect to `learn.chatgpt.com/docs/...`; content verified at the redirect target)

- Discovery order: global `~/.codex/AGENTS.override.md` or `~/.codex/AGENTS.md`, then from the **Git root down to the current directory**, checking each level for `AGENTS.override.md`, then `AGENTS.md`, then configured fallback names. Files are concatenated root-down; "files closer to your current directory override earlier guidance because they appear later in the combined prompt."
- **Timing:** discovery happens "once per run; in the TUI this usually means once per launched session." Content is capped at `project_doc_max_bytes` (default 32 KiB).
- **Config:** `~/.codex/config.toml` — `project_doc_fallback_filenames` (e.g. accept `TEAM_GUIDE.md`), `project_doc_max_bytes`.
- The doc describes AGENTS.md content as guidance/context, not hard constraints — advisory.

**Enforcement** — primary sources: [Codex — approvals & security / sandboxing](https://developers.openai.com/codex/security) and [Codex — hooks](https://learn.chatgpt.com/codex/hooks)

- **Approval policies:** untrusted / on-request / never. **Sandbox modes:** read-only, workspace-write, danger-full-access ("No sandbox; no approvals (not recommended)").
- Sandboxing is OS-level, enforced independently of the model: Seatbelt/`sandbox-exec` profiles on macOS, `bwrap` + `seccomp` on Linux, WSL2 or a native implementation on Windows. "By default, the agent runs with network access turned off"; enabling it requires `sandbox_workspace_write.network_access = true` or managed policy.
- **Hooks:** Codex now has a hooks framework — events include `PreToolUse`, `PostToolUse`, `PermissionRequest`, `UserPromptSubmit`, `SessionStart/End`, `SubagentStart/Stop`, `Stop`, `PreCompact`/`PostCompact`. Hooks can block ("to deny a request, return `{"hookSpecificOutput": {"decision": "deny"}}`"), rewrite tool inputs, and inject context. Configured in `~/.codex/hooks.json`, project `.codex/hooks.json`, `[hooks]` tables in `config.toml`, or plugin manifests; enterprise-managed enforcement exists via `requirements.toml`. (Event names closely mirror Claude Code's.)

**AGENTS.md:** honored natively — it is Codex's primary (and originating) instruction convention.

### OpenCode

**Guidance files** — primary source: [opencode.ai/docs/rules](https://opencode.ai/docs/rules/)

- On start, OpenCode looks for rule files in order: (1) local files by traversing up from the current directory — `AGENTS.md`, and `CLAUDE.md` as a compatibility fallback; (2) global `~/.config/opencode/AGENTS.md`; (3) `~/.claude/CLAUDE.md` (unless disabled). Loaded at session start; local files take precedence over global.
- `opencode.json` has an `instructions` field for additional instruction files (including remote URLs) merged with `AGENTS.md`.

**Enforcement** — primary sources: [permissions](https://opencode.ai/docs/permissions/), [plugins](https://opencode.ai/docs/plugins/)

- **Permissions:** per-tool rules (`read`, `edit`, `bash`, `webfetch`, `task`, `skill`, …) resolving to `allow` / `ask` / `deny`, with wildcard patterns, last-matching-rule-wins, and per-agent overrides. This is harness-side configuration (the docs don't spell out model-independence, but it is a config layer evaluated by the harness, not prose — same architecture as the other harnesses).
- **Plugins (hook equivalent):** JS/TS modules in `.opencode/plugins/` or `~/.config/opencode/plugins/` (or npm packages listed in `opencode.json`). Events include `tool.execute.before` / `tool.execute.after`, `permission.asked`/`replied`, session/message/file events. A plugin that **throws** in `tool.execute.before` blocks the tool call (docs' `.env`-protection example: `throw new Error("Do not read .env files")`).

**AGENTS.md:** honored natively as the primary rules file; also reads `CLAUDE.md` for Claude Code compatibility.

### Gemini CLI

**Guidance files** — primary sources: [Provide context with GEMINI.md files](https://geminicli.com/docs/cli/gemini-md/) (same content at [google-gemini.github.io](https://google-gemini.github.io/gemini-cli/docs/cli/gemini-md.html))

- **GEMINI.md**, three tiers: global `~/.gemini/GEMINI.md`; workspace — the CLI searches configured workspace directories *and their parent directories*; and just-in-time — "when a tool accesses a file or directory, the CLI automatically scans for `GEMINI.md` files in that directory and its ancestors up to a trusted root." All found files are concatenated and sent with every prompt; global/workspace tiers load at session start, JIT files on demand. `/memory show` and `/memory reload` inspect/refresh.
- **Imports:** `@file.md` syntax, relative or absolute paths.
- **Configurable filename:** `context.fileName` in `settings.json` accepts a string or array — the docs' own example is `"fileName": ["AGENTS.md", "CONTEXT.MD", "GEMINI.md"]` — so AGENTS.md support is native-with-one-setting, not default.

**Enforcement** — primary sources: [Gemini CLI hooks](https://geminicli.com/docs/hooks/), [enterprise guide](https://geminicli.com/docs/cli/enterprise/)

- **Hooks:** ten events (`SessionStart/End`, `BeforeAgent`/`AfterAgent`, `BeforeModel`/`AfterModel`, `BeforeToolSelection`, `BeforeTool`/`AfterTool`, `PreCompress`, `Notification`). `BeforeTool` supports block/rewrite; exit code 2 is a "System Block" that aborts the action with the stderr reason shown. Configured in `settings.json` at project (`.gemini/settings.json`), user (`~/.gemini/settings.json`), and system (`/etc/gemini-cli/settings.json`) layers, or via extensions.
- **Settings precedence** (highest first): system overrides → workspace `.gemini/settings.json` → user → system defaults; system settings paths per OS (`/etc/gemini-cli/settings.json`, `/Library/Application Support/GeminiCli/settings.json`, `C:\ProgramData\gemini-cli\settings.json`).
- **Tool restriction:** `tools.core` allowlist (e.g. `["ReadFileTool", "ShellTool(ls)"]`, recommended) vs `tools.exclude` blocklist (docs warn it is "less secure than allowlisting"); `mcp.allowed` allowlist for MCP servers; `security.disableYoloMode: true` forces confirmation for all tool executions; `tools.sandbox: "docker"` for container isolation. Approval modes exist (`--approval-mode` with a YOLO auto-approve mode that admins can disable).

**AGENTS.md:** not the default, but honored via a one-line `context.fileName` setting documented with AGENTS.md as the example value.

### Cursor

**Guidance files** — primary source: [cursor.com/docs/context/rules](https://cursor.com/docs/context/rules)

- **`.cursor/rules/*.mdc`** (version-controlled project rules) with frontmatter (`alwaysApply`, `description`, `globs`) giving four activation types: Always Apply (every session), Apply to Specific Files (glob match), Apply Intelligently (agent decides from description), Apply Manually (`@rule-name`). Plain `.md` files in `.cursor/rules` are ignored (no frontmatter). Rules are included "at the start of the model context" when their condition matches.
- **AGENTS.md:** supported natively, documented as a "simple alternative to `.cursor/rules`" — at project root and in subdirectories: "You can place `AGENTS.md` files in any subdirectory of your project, and they will be automatically applied when working with files in that directory or its children," with nested instructions combined and "more specific instructions taking precedence."
- **User Rules:** global, set in the app (not file-based).
- The current rules page no longer documents the legacy `.cursorrules` file; its historical deprecation in favor of `.cursor/rules` is **unverified from the current primary page** (widely reported, but the doc we fetched doesn't mention it).

**Enforcement** — primary sources: [rules](https://cursor.com/docs/context/rules), [hooks](https://cursor.com/docs/agent/hooks)

- **Hooks:** "Hooks let you observe, control, and extend the agent loop using custom scripts." Events include `preToolUse`/`postToolUse`, `beforeShellExecution`/`afterShellExecution`, `beforeMCPExecution`, `beforeReadFile`, `afterFileEdit`, `beforeSubmitPrompt`, `sessionStart/End`, `stop`, plus Tab and app-lifecycle hooks. Blocking: exit code 2 blocks the action (equivalent to `permission: "deny"`). Configured in `<project>/.cursor/hooks.json`, `~/.cursor/hooks.json`, or team/enterprise cloud-distributed config.
- **Team Rules:** "When enabled, the rule is required for all team members and cannot be disabled" — organizational enforcement of rule *presence* (the rule content itself is still advisory prompt text).

**AGENTS.md:** honored natively, root and nested.

---

## Synthesis

### Reach of each convention

| Convention | Claude Code | Codex | OpenCode | Gemini CLI | Cursor |
|---|---|---|---|---|---|
| `AGENTS.md` | via `@AGENTS.md` import or symlink (documented bridge) | **native** (primary) | **native** (primary) | native via `context.fileName` setting | **native** |
| `CLAUDE.md` | **native** (primary) | no | native (compat fallback) | via `context.fileName` | no |
| `GEMINI.md` | no | no | no | **native** (default) | no |
| `.cursor/rules/` | read once by `/init` (conversion, not live) | no | no | no | **native** |
| Skills (`SKILL.md`) | **native** (agentskills.io standard) | no (unverified — not in the docs fetched) | `skill` appears as a permission type in OpenCode docs; skill mechanism not researched here | extensions have a "skills" template (surfaced in search; **unverified** in detail) | no |
| Hooks that hard-block | **yes** (PreToolUse) | **yes** (PreToolUse) | **yes** (plugin `tool.execute.before` throw) | **yes** (BeforeTool, exit 2) | **yes** (preToolUse/beforeShellExecution, exit 2) |

**Winner on reach:** a repo-root `AGENTS.md`. Four of six read it natively or near-natively; Claude Code's own docs prescribe the two-line bridge; Gemini CLI needs one committed setting in `.gemini/settings.json`. No other single file comes close — `CLAUDE.md` reaches two harnesses natively, `GEMINI.md` one.

### Portable vs harness-specific

- **Portable:** prose guidance (root + nested AGENTS.md; nearest-file-wins is common semantics); the *pattern* of "concatenate ancestor files root-down, load subdirectory files on demand" (Claude Code, Codex, Gemini CLI, Cursor all implement a variant); the pattern of "pre-tool shell hook that can deny."
- **Harness-specific:** every hook/permission config schema and event vocabulary; path-scoped rule formats (`.mdc` frontmatter vs `paths:` YAML); skills; sandbox configuration; size caps (Codex 32 KiB project docs; Claude Code recommends <200 lines per CLAUDE.md).

### What can be enforced vs only communicated

- **Only communicated:** everything inside AGENTS.md/CLAUDE.md/GEMINI.md/rules files. All six primary docs treat instruction files as context; Claude Code's docs state the advisory nature explicitly, and agents.md offers no mechanism at all.
- **Enforceable in-harness:** a deterministic CLI check invoked from each harness's blocking hook (Claude Code `PreToolUse`, Codex `PreToolUse`, Gemini CLI `BeforeTool`, Cursor `preToolUse`/`beforeShellExecution`, OpenCode plugin `tool.execute.before`) — all five can veto a tool call before it runs, independent of the model's cooperation. Harness permission systems (Claude Code deny rules, Codex sandbox/approvals, OpenCode permissions, Gemini `tools.core`) can additionally hard-limit tool/file/network access, but they gate *capabilities*, not project-semantic rules — a SMAIRT-style semantic contract check has to be a script the hook runs.
- **Enforceable for everyone:** CI. Hooks are per-machine config that a user can remove or that a harness outside this survey won't run; CI running the same CLI check is the only floor that binds all contributors and all agents.

### Recommendation shape for SMAIRT

The evidence supports the proposed architecture: one canonical machine-readable contract, rendered/bridged into:
1. `AGENTS.md` (generated or hand-maintained) — the prose surface; reaches Codex, OpenCode, Cursor natively, plus nested per-directory variants where useful.
2. `CLAUDE.md` containing `@AGENTS.md` + Claude-specific notes (documented Anthropic pattern).
3. `.gemini/settings.json` with `context.fileName: ["AGENTS.md", "GEMINI.md"]` (documented Google pattern).
4. One `smairt check`-style CLI, wired identically into `.claude/settings.json` hooks, `.codex/hooks.json`, `.gemini/settings.json` hooks, `.cursor/hooks.json`, and an OpenCode plugin — all five block on nonzero/deny — plus CI as the universal enforcement floor.

Advisory text is duplicated zero times (single AGENTS.md, thin imports); enforcement logic is written once (the CLI) with per-harness wiring being the only genuinely harness-specific artifact.

---

## Sources (primary)

- Claude Code memory / CLAUDE.md / rules / AGENTS.md guidance: https://code.claude.com/docs/en/memory
- Claude Code skills: https://code.claude.com/docs/en/skills (skills standard: https://agentskills.io)
- Claude Code hooks: https://code.claude.com/docs/en/hooks
- Claude Code permissions: https://code.claude.com/docs/en/permissions
- AGENTS.md standard: https://agents.md/
- OpenAI Codex — AGENTS.md guide: https://developers.openai.com/codex/guides/agents-md (308-redirects to https://learn.chatgpt.com/docs/agent-configuration/agents-md)
- OpenAI Codex — security/approvals/sandboxing: https://developers.openai.com/codex/security (redirect target: https://learn.chatgpt.com/codex/agent-approvals-security)
- OpenAI Codex — hooks: https://learn.chatgpt.com/codex/hooks
- OpenCode rules: https://opencode.ai/docs/rules/
- OpenCode permissions: https://opencode.ai/docs/permissions/
- OpenCode plugins: https://opencode.ai/docs/plugins/
- Gemini CLI context files (GEMINI.md): https://geminicli.com/docs/cli/gemini-md/ (mirror: https://google-gemini.github.io/gemini-cli/docs/cli/gemini-md.html)
- Gemini CLI hooks: https://geminicli.com/docs/hooks/
- Gemini CLI enterprise/enforcement: https://geminicli.com/docs/cli/enterprise/
- Cursor rules: https://cursor.com/docs/context/rules
- Cursor hooks: https://cursor.com/docs/agent/hooks

### Unverified items

- Legacy `.cursorrules` deprecation: not present on the current primary rules page; treated as historical/unverified.
- Codex skills support: not covered by the pages fetched; no claim made.
- Gemini CLI extensions "skills" template: surfaced only in search snippets, not verified against a primary page.
- OpenCode permission enforcement being fully model-independent: the docs describe a harness-evaluated allow/ask/deny layer but don't state model-independence explicitly.
- The `learn.chatgpt.com` domain as the canonical new home of Codex docs: inferred from the 308 permanent redirects observed on developers.openai.com/codex URLs; the redirect target served the content quoted.
