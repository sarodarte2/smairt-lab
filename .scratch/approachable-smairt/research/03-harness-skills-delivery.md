# 03 — Where each harness loads project-local, agent-invocable procedures from

Research ticket: [`issues/03-harness-skills-delivery.md`](../issues/03-harness-skills-delivery.md).
Establishes, from each vendor's own documentation, the project-local *skills*
surface for the six harnesses `smairt connect` supports — so the Q5 charting
decision ("`smairt connect` installs SMAIRT's skills alongside the hooks it
already writes") can be implemented against facts.

Sources are primary: official docs sites, or the tool's own docs in its own
repository. Fetched **2026-08-19**. Every claim that could not be traced to a
primary source is marked **unverified** and collected at the bottom.

Companion to [`practical-smairt/research/10-harness-guidance-conventions.md`](../../practical-smairt/research/10-harness-guidance-conventions.md),
which surveyed the same harnesses for *hooks and instruction files*. Changes
since that survey are noted in "What changed since file 10".

---

## Short answer

1. **There is no null result. All six harnesses have a project-local,
   agent-invocable skills surface**, and all six converged on the same
   artifact: a directory containing a `SKILL.md` with YAML frontmatter, per the
   [Agent Skills](https://agentskills.io) open standard. File 10's synthesis
   table — which listed skills as "**Not portable**", native to Claude Code
   only — is **now wrong**. This is the single biggest change since that survey.

2. **`.agents/skills/` is the near-universal project-local path.** Five of six
   read it: Codex (its *only* repo path), Cursor, OpenCode, Gemini CLI (as a
   documented alias that *outranks* `.gemini/skills/`), and pi. The one holdout
   is **Claude Code**, whose docs list only `.claude/skills/` — the same shape
   as the `AGENTS.md`/`CLAUDE.md` split file 10 found. So the reach story is
   identical to the prose-contract story: one canonical location plus one
   Claude-shaped copy covers everything.

3. **Frontmatter is portable at the two-field core.** `name` + `description` is
   accepted by all six; four of six (Codex, Cursor, OpenCode, pi) require both.
   Claude Code alone makes every field optional. Cursor, OpenCode and Gemini
   CLI require or recommend `name` to match the parent directory name — SMAIRT's
   existing `skills/smairt-*/SKILL.md` files already satisfy this.

4. **Invocation is "model decides, user can force" everywhere.** Every harness
   injects only `name` + `description` at session start (progressive
   disclosure) and loads the body on demand. Five of six also give the user an
   explicit handle (`/skill-name` in Claude Code and Cursor, `$mention` /
   `/skills` in Codex, `/skill:name` in pi, `/skills` in Gemini CLI). OpenCode
   is the only one with **no user-facing invocation** — the agent calls a
   native `skill` tool. Nothing has to be *registered* anywhere: dropping the
   directory in the right place is the whole installation.

5. **Trust gating splits the field.** Claude Code (explicitly), Cursor, Codex
   and Gemini CLI load project skills without an opt-in. **pi** loads project
   skills *only after the project is trusted* — documented, and it names
   `.agents/skills` specifically. Gemini CLI adds a per-activation consent
   prompt rather than a per-install one. This matters for the generated
   notices: the file 10 caveat SMAIRT already prints for Codex hooks belongs on
   **pi's** skills, not (as far as the docs say) on Codex's.

6. **Multi-file skills are supported by five of six**, with the same
   `scripts/` / `references/` / `assets/` convention documented by Codex,
   Cursor, Gemini CLI and pi. OpenCode's docs simply don't address it. SMAIRT's
   eight skills are single-file (11.7 KB total), so this constrains nothing
   today.

7. **Blocking implementation fact, found in this repo, not in the docs:**
   `skills/` is **not shipped in the package**. `pyproject.toml` builds the
   wheel from `packages = ["src/smairt"]` and the sdist from an include list
   that does not name `/skills`. A pip-installed `smairt connect` today has no
   access to the skill bytes at all. Whatever else is decided, the skills must
   move under `src/smairt/` (e.g. `src/smairt/assets/skills/`) before this
   ticket's feature can work outside a source checkout.

---

## Per-harness table

| | Surface exists? | Project-local path | Format / required metadata | Invocation | Project files trusted by default? | Multi-file? |
|---|---|---|---|---|---|---|
| **claude-code** | **Yes** — "Skills" | `.claude/skills/<name>/SKILL.md` (also every parent dir up to repo root; nested dirs load on first touch) | `SKILL.md` + YAML frontmatter. **All fields optional**; `description` "recommended". Many CC-only extras (`disable-model-invocation`, `allowed-tools`, `paths`, …) | Auto (model-chosen from `description`) **and** `/<dir-name>`. Directory name is the command | **Yes.** "Workspace trust doesn't gate this field… including in a `-p` run in a folder you've never trusted" | **Yes** — `SKILL.md` required, plus templates / `examples/` / `scripts/` / `references/`, referenced by relative link |
| **codex** | **Yes** — "Skills" | `.agents/skills/<name>/SKILL.md` — scanned in every dir from cwd up to repo root. **Not** `.codex/skills/` | `SKILL.md` + frontmatter; `name` and `description` **required** | Auto (matches on `description`), `$` mention in CLI/IDE, `/skills` command. Restart Codex after adding | Docs describe no trust gate or feature flag for repo skills (see unverified #2) | **Yes** — `scripts/`, `references/`, `assets/`, optional `agents/openai.yaml` |
| **cursor** | **Yes** — "Agent Skills" | `.agents/skills/<name>/SKILL.md` **and** `.cursor/skills/<name>/SKILL.md`; also reads `.claude/skills/` and `.codex/skills/` for compat; nested dirs auto-scoped | `SKILL.md` + frontmatter. **`name` required** (lowercase/digits/hyphens, *must match parent folder*), **`description` required**. Optional `paths`, `disable-model-invocation`, `icon`, `color`, `metadata` | Auto by default ("the agent is presented with available skills and decides when they are relevant"); user types `/` and picks. `disable-model-invocation: true` makes it user-only | Docs describe no trust/opt-in step | **Yes** — `scripts/`, `references/`, `assets/` |
| **opencode** | **Yes** — "Agent Skills" | `.opencode/skills/<name>/SKILL.md`; also `.claude/skills/` and `.agents/skills/`. Walks up from cwd to the git worktree | `SKILL.md` (caps enforced) + frontmatter. Recognized fields *only*: `name` (**required**, 1–64 chars, `^[a-z0-9]+(-[a-z0-9]+)*$`, **must match directory**), `description` (**required**, 1–1024 chars), `license`, `compatibility`, `metadata`. Unknown fields ignored | **Model only.** Agent calls the native tool: `skill({ name: "git-release" })`. No slash command documented | Governed by `permission.skill` patterns in `opencode.json` (`allow`/`deny`/`ask`). Docs say "Most permissions default to `allow`" but don't name `skill`'s default (unverified #3) | **Not documented.** Docs cover only `SKILL.md` placement (unverified #4) |
| **gemini-cli** | **Yes** — "Agent Skills" | `.gemini/skills/<name>/SKILL.md`, or the `.agents/skills/` alias — and *"the `.agents/skills/` alias takes precedence"* | `SKILL.md` + YAML frontmatter with `name` ("should match the directory name") and `description` (**"CRITICAL"** — the trigger signal) | Auto: names+descriptions injected at session start; model calls the `activate_skill` tool; **then a consent prompt** naming the skill and the directory it gains access to. Managed via `/skills …` and `gemini skills …` | Yes for *discovery* — no install step, no flag documented. But **activation raises a per-use confirmation prompt**, and the skill dir is only then added to the agent's allowed file paths | **Yes** — `scripts/`, `references/`, `assets/`; "the model is granted access to this entire directory" on activation |
| **pi** | **Yes** — "Skills" | `.pi/skills/` **and** `.agents/skills/` in cwd + ancestors up to the git root — **"only after the project is trusted"** | `SKILL.md` + frontmatter per the Agent Skills spec. `name` **required** (≤64 chars, lowercase/digits/hyphens; pi deliberately does *not* require it to match the directory), `description` **required** (≤1024). Optional `license`, `compatibility`, `metadata`, `allowed-tools`, `disable-model-invocation` | Auto: names+descriptions in the system prompt, agent `read`s the full file. Plus `/skill:name [args]` commands, controlled by `enableSkillCommands` (**default `true`**) | **No — explicit trust required.** "On interactive startup, pi asks before trusting a project folder that contains project-local settings, resources, or project `.agents/skills`". Non-interactive modes (`-p`, `--mode json`, `--mode rpc`) never prompt and fall back to `defaultProjectTrust` (default `ask` ⇒ **ignored**) | **Yes** — "A skill is a directory with a `SKILL.md` file. Everything else is freeform." Documents `scripts/`, `references/`, `assets/` |

---

## Per-harness detail

### claude-code

Primary source: [Extend Claude with skills](https://code.claude.com/docs/en/skills).

- **Path.** The doc's scope table gives `Project → .claude/skills/<skill-name>/SKILL.md → This project only`. Discovery: *"Project skills load from `.claude/skills/` in the directory where you start Claude Code and in every parent directory up to the repository root."* Nested `.claude/skills/` below the start directory *"load the first time Claude reads or edits a file inside that subdirectory."*
- **No `.agents/skills/` support is documented.** The scope table lists only enterprise / personal / project / plugin locations, and the string `.agents` does not appear on the page. Treat Claude Code as the one harness that needs its own copy.
- **Frontmatter.** *"All fields are optional. Only `description` is recommended so Claude knows when to use the skill."* `name` is only a display label for personal/project skills — *"the command still comes from the directory name."*
- **Invocation.** *"Claude uses skills when relevant, or you can invoke one directly with `/skill-name`."* `disable-model-invocation: true` → user-only; `user-invocable: false` → model-only.
- **Trust.** Explicit and unusually direct: *"Workspace trust doesn't gate this field. Claude Code applies a project skill's `allowed-tools` whenever you or Claude invoke the skill, including in a `-p` run in a folder you've never trusted."* The doc frames this as a hazard — *"review the `allowed-tools` of skills checked into a repository before you run Claude Code there."* SMAIRT's skills declare no `allowed-tools`, which is the right posture to keep.
- **Multi-file.** *"The `SKILL.md` contains the main instructions and is required. Other files are optional"* — templates, `examples/`, `scripts/`, `references/`. *"Reference supporting files from `SKILL.md` so Claude knows what each file contains and when to load it."* Keep `SKILL.md` under 500 lines.
- **Live reload.** Claude Code watches project `.claude/skills/`, so a `smairt connect` run mid-session takes effect without a restart.

### codex

Primary source: [Build skills](https://learn.chatgpt.com/docs/build-skills) (`https://developers.openai.com/codex/skills` 308-redirects there; `openai/codex`'s own `docs/skills.md` is a three-line stub pointing at the same page).

- **Path is `.agents/skills`, not `.codex/skills`.** Discovery order: `$CWD/.agents/skills`, `$CWD/../.agents/skills` (parent folders in Git repos), `$REPO_ROOT/.agents/skills`, `$HOME/.agents/skills`, `/etc/codex/skills`, then built-ins.
- **Frontmatter.** `name` and `description` required; the doc's guidance for `description` is *"Explain exactly when this skill should and should not trigger."*
- **Invocation.** Three ways: implicit (*"Codex can choose a skill when your task matches the skill `description`"*), `$` mention in the CLI/IDE, and the `/skills` command. **Restart Codex after installing or updating a skill** — unlike Claude Code, there's no documented live reload. `smairt connect codex` should say so.
- **Trust / flags.** The page documents `[[skills.config]]` entries in `~/.codex/config.toml` to *disable* a named skill, implying skills are on by default, and says nothing about a repo-trust gate or feature flag. See unverified #2 — there is contrary non-primary signal.
- **Multi-file.** `scripts/`, `references/`, `assets/`, and an optional `agents/openai.yaml`.

### cursor

Primary source: [Agent Skills](https://cursor.com/docs/skills) (markdown at `https://cursor.com/docs/skills.md`).

- **Paths.** Project: `.agents/skills/` and `.cursor/skills/`. Global: `~/.agents/skills/`, `~/.cursor/skills/`. *"For compatibility, Cursor also loads skills from Claude and Codex directories: `.claude/skills/`, `.codex/skills/`, `~/.claude/skills/`, and `~/.codex/skills/`."* — so a Cursor user picks up SMAIRT's skills no matter which of the two paths `connect` writes.
- **Nested scoping.** A `.cursor/skills/` or `.agents/skills/` anywhere in the repo is picked up and *"automatically scoped to files inside that directory."*
- **Frontmatter.** `name` **required** — *"Lowercase letters, numbers, and hyphens only. Must match the parent folder name."* `description` **required**. Optional `paths` (glob scoping), `disable-model-invocation`, `icon`, `color`, `metadata`.
- **Invocation.** Auto by default; `/` in Agent chat to pick manually. Slash commands are now *implemented as* skills: *"Both user-level and workspace-level commands are converted to skills with `disable-model-invocation: true`."*
- **Multi-file.** `scripts/` (any language), `references/`, `assets/`.
- **Relationship to `.cursor/rules/`.** Rules still exist (file 10's finding holds), but the docs now position skills as the surface for *"multi-step workflows"* and rules for always-on conventions. `connect.py`'s existing `.cursor/rules/smairt.mdc` and a new skills install are complementary, not redundant.

### opencode

Primary source: [Agent Skills](https://opencode.ai/docs/skills/).

- **Paths.** `.opencode/skills/<name>/SKILL.md`, `~/.config/opencode/skills/…`, `.claude/skills/<name>/SKILL.md`, `~/.claude/skills/…`, `.agents/skills/<name>/SKILL.md`, `~/.agents/skills/…`. *"For project-local paths, OpenCode walks up from your current working directory until it reaches the git worktree."*
- **Frontmatter is a closed set.** *"Only these fields are recognized: `name` (required), `description` (required), `license`, `compatibility`, `metadata`. Unknown frontmatter fields are ignored."* `name` must match the containing directory and match `^[a-z0-9]+(-[a-z0-9]+)*$`; `description` 1–1024 chars.
- **Invocation is model-only.** *"Skills are loaded on-demand via the native `skill` tool"*; the agent calls `skill({ name: "git-release" })`. Names and descriptions are advertised in an `<available_skills>` block inside the tool description. No user slash command is documented — the one harness where SMAIRT cannot tell a researcher "type `/smairt-orient`".
- **Permissions.** `permission.skill` patterns in `opencode.json` resolve to `allow` / `deny` / `ask`; `deny`d skills are *"hidden from agents"*. An agent can disable the tool entirely with `tools: { skill: false }`.
- **Troubleshooting checklist** (worth mirroring in `connect`'s output): `SKILL.md` in all caps, frontmatter has `name` and `description`, names unique across all locations, no `deny` permission.

### gemini-cli

Primary sources: [Agent Skills](https://geminicli.com/docs/cli/skills/) and [Creating Agent Skills](https://geminicli.com/docs/cli/creating-skills/) (identical text in `google-gemini/gemini-cli` `docs/cli/skills.md` and `docs/cli/creating-skills.md`).

- **Paths.** Four discovery tiers, lowest→highest precedence: built-in, extension, user (`~/.gemini/skills/` or `~/.agents/skills/`), workspace (`.gemini/skills/` or `.agents/skills/`). *"Workspace skills are shared with your team via version control."* And critically: *"Within the same tier (user or workspace), the `.agents/skills/` alias takes precedence over the `.gemini/skills/` directory."*
- **Frontmatter.** `name` — *"A unique identifier for the skill. This should match the directory name."* `description` — *"**CRITICAL.** This is how Gemini decides when to use the skill."*
- **Invocation and consent.** The documented lifecycle is discovery → activation (`activate_skill` tool) → **consent** (*"You will see a confirmation prompt in the UI detailing the skill's name, purpose, and the directory path it will gain access to"*) → injection (body + folder structure enters history; the skill dir joins the agent's allowed file paths) → execution. So Gemini CLI's opt-in is **per activation**, not per install. Management: `/skills list|link|disable|enable|reload` and `gemini skills list|install|uninstall`.
- **Multi-file.** `scripts/`, `references/`, `assets/`; *"When a skill is activated, the model is granted access to this entire directory."*
- **Note for `connect.py`.** Gemini CLI is the harness whose *hook* wiring `connect.py` still flags as best-effort. Its *skills* surface, by contrast, is fully documented and needs no inference — the skills half of `_connect_gemini` can be written with the same confidence as the others.

### pi

Primary sources: [`packages/coding-agent/docs/skills.md`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/skills.md) and [`docs/settings.md`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/settings.md) in the pi repo.

- **This is new relative to `connect.py`.** The module's pi comment block describes only `.pi/extensions/*.ts`. pi has a first-class skills surface: *"Pi implements the [Agent Skills standard](https://agentskills.io/specification), warning about most violations but remaining lenient."*
- **Paths.** Global `~/.pi/agent/skills/`, `~/.agents/skills/`. Project — *"only after the project is trusted"* — `.pi/skills/` and *"`.agents/skills/` in `cwd` and ancestor directories (up to git repo root)"*. Also packages, a `skills` array in settings, and `--skill <path>`.
- **Discovery quirk that matters.** In `~/.pi/agent/skills/` and `.pi/skills/`, *bare* root `.md` files count as skills if they carry valid frontmatter; in `.agents/skills/`, *"root `.md` files are ignored, but nested `.md` files in grouping folders are discovered."* Directories containing `SKILL.md` are discovered recursively in **all** locations — so the standard `<name>/SKILL.md` layout is safe everywhere.
- **Frontmatter.** `name` and `description` required, with the spec's limits. Deliberate divergence: *"Pi does not require the name to match the parent directory… that standard requirement is suboptimal for shared skill directories used across multiple agent harnesses."*
- **Invocation.** Names+descriptions in the system prompt per the spec's XML format; the agent `read`s the full file. Candid caveat in the docs: *"models don't always do this; use prompting or `/skill:name` to force it."* `/skill:name <args>` appends args as `User: <args>`; the whole command surface is toggled by `enableSkillCommands` (default `true`).
- **Trust, precisely.** *"On interactive startup, pi asks before trusting a project folder that contains project-local settings, resources, or project `.agents/skills`."* Non-interactive modes never prompt: *"Without an applicable saved trust decision, they use `defaultProjectTrust` from global settings: `ask` (default) and `never` ignore those project resources, while `always` trusts them."* So in `pi -p` runs, an untrusted project's SMAIRT skills are **silently absent**. `/trust` persists a decision; a restart is required for it to take effect.
- **Security note the docs lead with**, worth echoing in generated output: *"Skills can instruct the model to perform any action and may include executable code the model invokes. Review skill content before use."*

---

## What changed since file 10

| File 10 claim | Status now |
|---|---|
| "*Not portable:* skills (Claude Code / agentskills.io …)" | **Superseded.** All six harnesses implement the Agent Skills standard with a project-local path. |
| "Codex — skills: no (unverified — not in the docs fetched)" | **Resolved: yes**, at `.agents/skills`, fully documented. |
| "OpenCode — `skill` appears as a permission type…; skill mechanism not researched" | **Resolved:** `.opencode/skills/`, `.claude/skills/`, `.agents/skills/`; native `skill` tool. |
| "Gemini CLI extensions have a 'skills' template (**unverified**)" | **Superseded by something bigger:** Gemini CLI has first-class Agent Skills with `.gemini/skills/` + `.agents/skills/` alias, `/skills` and `gemini skills` commands. |
| "Cursor — skills: no" | **Superseded: yes**, `.cursor/skills/` + `.agents/skills/`, and slash commands are now implemented as skills. |
| pi was not in file 10's survey at all | Covered here; has both extensions (already wired) and skills (not wired). |
| Hooks/instruction-file findings | No contradictions found. `.cursor/rules/*.mdc`, `AGENTS.md` reach, `context.fileName`, plugin/extension hook shapes all still stand as documented. |

---

## Recommendation for `_HARNESS_HANDLERS`

### 0. Prerequisite: ship the skills

`skills/smairt-*/SKILL.md` is not in the wheel (`[tool.hatch.build.targets.wheel] packages = ["src/smairt"]`) or the sdist include list. **Move the eight skills to `src/smairt/assets/skills/<name>/SKILL.md`** and read them with `importlib.resources`. Without this, the feature works only from a source checkout. This is a precondition, not a nice-to-have.

### 1. Copy, not reference — and it isn't close

The ticket asks copy-vs-reference. **Copy.** Reasons, in order of weight:

1. **Reference is not expressible in four of six harnesses.** There is no project-local "also read skills from this path" config in Claude Code (`--add-dir` is a launch-time flag, not a committed file), Cursor, OpenCode (`opencode.json` documents no skills-path key), or Codex (`[[skills.config]]` disables named skills; it doesn't add search roots). Only pi (`.pi/settings.json` `skills: ["…"]`) and Gemini CLI (`/skills link`, interactive) can reference. A reference strategy would mean two harnesses work and four don't — the exact "pretend" outcome the ticket forbids.
2. **A reference would point at a path that moves.** `site-packages/smairt/assets/skills/…` differs per venv, per machine, per collaborator. A committed file naming it breaks for the second person who clones the repo — and SMAIRT projects are meant to be shared artifacts.
3. **Copies are cheap and honest here.** Eight files, 11.7 KB total, no supporting files. They land in the project, get committed, are readable, and are deletable — exactly the property every other file `connect.py` writes already has.
4. **Copies survive `pip uninstall smairt`.** A project's recorded procedures shouldn't evaporate when a tool is removed from one laptop.

**Drift is the cost, and it must be reported, not hidden.** The existing policy (identical → `skipped`, different → `warned`, left untouched) already handles this correctly in mechanism but not in message: an *outdated* SMAIRT skill and a *researcher-edited* SMAIRT skill are indistinguishable by content, and both currently produce the same generic warning. Two mitigations:

- Put a provenance line in the generated `SKILL.md` body — `<!-- Generated by smairt connect <harness> (smairt X.Y.Z). Delete this directory to remove it; re-run connect to reinstall. -->` — so a reader can see which version they have.
- Make the warning for skill files say the concrete remedy: *"differs from the skill shipped with smairt X.Y.Z — left untouched. If you didn't edit it, delete it and re-run `smairt connect <harness>` to update."* This is the same "delete and re-run" story `strict_hooks` already documents, so it's a consistent idiom rather than a new one.

### 2. Write to two paths, keyed by harness — not six

The dispatch table stays per-harness (parity, foundation 8), but the *targets* collapse to two:

| Harness | Skills target |
|---|---|
| `claude-code` | `.claude/skills/<name>/SKILL.md` |
| `codex`, `cursor`, `opencode`, `gemini-cli`, `pi` | `.agents/skills/<name>/SKILL.md` |

This falls out of the docs, not from a preference: `.agents/skills/` is Codex's only repo path, Gemini CLI's *higher-precedence* alias, and a documented location for Cursor, OpenCode and pi. Claude Code documents no `.agents/` support.

Two properties worth noting:

- **Connecting several harnesses is free.** The second `smairt connect` targeting `.agents/skills/` finds byte-identical files and reports `skipped`. No duplication, no conflict — the existing idempotency rule does the work.
- **Cursor and OpenCode also read `.claude/skills/`**, so a project connected only to `claude-code` still gives those two the skills incidentally. Don't rely on it; do mention it if it simplifies a researcher's mental model.

Implementation shape — one shared helper, six one-line call sites, matching how `_report_notice` / `_ts_header` already factor shared text:

```python
_SKILLS_TARGETS: dict[Harness, str] = {
    Harness.claude_code: ".claude/skills",
    Harness.codex:       ".agents/skills",
    Harness.cursor:      ".agents/skills",
    Harness.opencode:    ".agents/skills",
    Harness.gemini_cli:  ".agents/skills",
    Harness.pi:          ".agents/skills",
}

def _install_skills(project_root, harness, builder) -> None:
    """Copy SMAIRT's shipped skills into `harness`'s project-local skills dir."""
    root = _SKILLS_TARGETS[harness]
    for name, body in _shipped_skills():          # importlib.resources
        _write_or_warn(project_root, f"{root}/{name}/SKILL.md", body, builder)
```

Each `_connect_<harness>` gains one `_install_skills(...)` line. `_guard_project_scoped` already covers the new paths unchanged. `ConnectResult` needs no change — skill paths are just more entries in `written`/`skipped`/`warned`.

### 3. Frontmatter: tighten to the intersection, once

SMAIRT's skills already carry exactly `name` + `description` and already use `name == directory name`. Keep that and **don't add harness-specific fields** — no `allowed-tools` (Claude Code's docs flag repo-committed `allowed-tools` as a review hazard and it bypasses workspace trust), no `disable-model-invocation`, no `paths`. The two-field intersection loads unmodified in all six. Worth encoding as a test: a `tests/` assertion that every shipped `SKILL.md` has lowercase-hyphen `name` matching its directory, a `description` ≤ 1024 chars, and no other frontmatter keys. That single test enforces Cursor's, OpenCode's and pi's validators at once.

One content change is needed regardless: `skills/smairt-adversarial-review` says "Researcher-invoked only — never run this unprompted" in prose. In four harnesses that's only advisory. Since the field that would enforce it (`disable-model-invocation`) is not portable (unsupported in OpenCode and Gemini CLI, unknown to the spec's core), keep it as prose but strengthen the `description` to state it — `description` is the only field every harness actually acts on.

### 4. Degrade honestly — not for a missing surface, but for three real gaps

No harness needs a "we can't do this here" path. Three do need an honest caveat in `connect`'s output:

- **pi — trust.** Project `.agents/skills` load only after the project is trusted, and non-interactive runs (`pi -p`, `--mode json`, `--mode rpc`) with the default `defaultProjectTrust: "ask"` **ignore them silently**. `smairt connect pi` should print: *"pi loads these only after you trust this project — accept the trust prompt on your next interactive start, or run `/trust`. Non-interactive `pi -p` runs ignore project skills unless `defaultProjectTrust` is `always`."*
- **codex — restart.** *"After installing or updating a skill, restart Codex so it reloads metadata."* Say so; Claude Code by contrast hot-reloads and Cursor/OpenCode/Gemini have `/skills reload`-style paths.
- **opencode — no user handle.** There is no `/smairt-orient` in OpenCode; the agent decides. Say that plainly rather than printing a slash command that doesn't exist. Conversely, the printed handles differ per harness — `/smairt-orient` (Claude Code, Cursor), `$smairt-orient` or `/skills` (Codex), `/skill:smairt-orient` (pi), `/skills list` (Gemini CLI). If `connect`'s output names a handle at all, it must name the right one per harness.

Also flag Gemini CLI's per-activation consent prompt so a researcher isn't surprised by it, and note that Codex/Cursor/OpenCode/Gemini all read *other* harnesses' skill directories — meaning a researcher who has already connected one harness may see SMAIRT's skills appear in another before running `connect` for it.

### 5. Follow-on for the map's open question

The map lists "`docs/AI_SKILL_USAGE.md`'s fate" as unspecified. This research settles the substance: that document exists to say "make `skills/` available to an assistant somehow", which is precisely what `connect` will now do, per harness, with the real paths. Once implemented, its content is either wrong or redundant — it should be deleted, with the per-harness paths going into `docs/REFERENCE.md`'s harness matrix (Q7 decision).

---

## Sources (primary)

- Claude Code — Extend Claude with skills: https://code.claude.com/docs/en/skills
- Agent Skills open standard: https://agentskills.io — spec: https://agentskills.io/specification
- OpenAI Codex — Build skills: https://learn.chatgpt.com/docs/build-skills (via 308 from https://developers.openai.com/codex/skills); repo stub: https://github.com/openai/codex/blob/main/docs/skills.md
- Cursor — Agent Skills: https://cursor.com/docs/skills (markdown source: https://cursor.com/docs/skills.md)
- OpenCode — Agent Skills: https://opencode.ai/docs/skills/
- OpenCode — Permissions: https://opencode.ai/docs/permissions/
- Gemini CLI — Agent Skills: https://geminicli.com/docs/cli/skills/ (repo: https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/skills.md)
- Gemini CLI — Creating Agent Skills: https://geminicli.com/docs/cli/creating-skills/ (repo: https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/creating-skills.md)
- pi — Skills: https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/skills.md
- pi — Settings (project trust, `enableSkillCommands`): https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/settings.md
- pi — Extensions (trust flow, `project_trust`, `skillPaths`): https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/extensions.md

### Unverified items

1. **Claude Code and `.agents/skills/`.** The skills page lists only enterprise / `~/.claude/skills/` / `.claude/skills/` / plugin locations and never mentions `.agents`. Absence of a claim, not a documented denial — but the recommendation depends on it, so it should be re-checked if Claude Code's docs change. A cheap empirical check (drop a skill in `.agents/skills/` and run `/skills`) would settle it.
2. **Codex repo-skill trust / feature flag.** The primary page documents no flag and no trust gate. Non-primary signal points the other way: a web search surfaced claims of `codex features list`, `codex --enable skills`, and `[features] skills = true` in `config.toml`, and an issue in the vendor's own tracker — [openai/codex#16012, "Repo-local .agents/skills skill is not injected into session"](https://github.com/openai/codex/issues/16012) — reports repo-local skills failing to load. Neither was verified against the documentation. **Treat Codex repo-local skill loading as the one delivery path to smoke-test by hand before trusting it.**
3. **OpenCode's default `permission.skill`.** The permissions doc says *"Most permissions default to `allow`"* with `doom_loop` and `external_directory` as the named exceptions; it does not name `skill`'s default. Almost certainly `allow`, not confirmed.
4. **OpenCode multi-file skills.** The docs describe only `SKILL.md` placement and say nothing about `scripts/` / `references/` / `assets/`. Since the skill body is injected and the agent has normal file tools, relative references would likely work — untested and undocumented. Irrelevant while SMAIRT's skills stay single-file.
5. **Gemini CLI frontmatter as a hard requirement.** The docs consistently show `name` + `description` and call `description` "CRITICAL", and say `name` "should match the directory name" — but never state a validator that rejects a file lacking them. Treated as required here because every other harness requires them anyway.
6. **`learn.chatgpt.com` as the canonical home of Codex docs** — inherited unverified item from file 10; the 308 redirect from `developers.openai.com/codex/skills` was observed again on 2026-08-19 and the target served the quoted content.

---

## Verification pass — Context7 (primary sources)

Re-checked the five unverified claims against Context7's indexed primary docs and
source. Results below supersede the "could not verify" list above.

### Codex — CONFIRMED at implementation level, doubt largely retired

`codex-rs/core-skills/src/loader.rs` (`repo_agents_skill_roots`) walks every
directory between cwd and project root, probes each for `.agents/skills/`, and
registers what it finds with `scope: SkillScope::Repo` and
`discovery_mode: SkillDiscoveryMode::Recursive`. The path is real and shipped —
not aspirational.

- Source: https://github.com/openai/codex/blob/main/codex-rs/core-skills/src/loader.rs
- **No feature flag gates it.** Nothing ties skills to `experimentalFeature/list`;
  the non-primary `[features] skills = true` claim is unsupported.
- **Trust probably does not gate it.** Codex's own trust prompt enumerates what
  trusting enables — "project-local config, hooks, and exec policies" — and does
  **not** name skills.
  Source: https://github.com/openai/codex/blob/main/codex-rs/tui/src/onboarding/trust_directory.rs
- Tracker issue [codex#16012](https://github.com/openai/codex/issues/16012) is
  therefore most likely a fixed or environment-specific bug, not a missing
  feature. **Keep the smoke-test in ticket 09, but as a sanity check rather than
  a go/no-go gate.**

### Claude Code — `.agents/skills/` negative evidence strengthened

Official docs enumerate skill locations and `.agents/skills/` is **not** among
them; `.claude/skills/<name>/SKILL.md` is the project surface, and nested
`.claude/skills/` directories load when working on files beneath them (name
clashes render as `<dir>:<name>`). Still absence rather than denial, but the
enumeration makes it a much stronger negative. **The two-path dispatch
(`.claude/skills/` for Claude Code, `.agents/skills/` for the other five) is
confirmed as the right design.**

- Source: https://code.claude.com/docs/en/skills
- Source: https://code.claude.com/docs/en/large-codebases

### OpenCode — search locations confirmed, default still unstated

Official docs confirm all six search locations, including
`.agents/skills/<name>/SKILL.md`. `permission.skill` is documented and richer
than assumed — it takes **per-skill glob patterns**
(`{"*": "allow", "internal-*": "deny", "experimental-*": "ask"}`), not just a
scalar. The **default value remains unstated** in the docs; treat as unverified.
Native support is confirmed, so the third-party `opencode-skills` plugin is not
required.

- Source: https://opencode.ai/docs/skills
- Source: https://opencode.ai/docs/tools

### NEW FINDING — both major harnesses can enforce researcher-invoked-only

Not sought, but directly relevant to SMAIRT's contract:

- **Claude Code** supports `disable-model-invocation: true` in SKILL.md
  frontmatter — "restricts invocation to only the user... Claude cannot
  automatically trigger these skills."
- **Codex** supports an optional `agents/openai.yaml` inside a skill folder
  carrying "UI metadata and **invocation policy**". SMAIRT already shipped files
  at exactly this path in v1 (`skills/smairt-paper-driven/agents/openai.yaml`),
  deleted in the v2 rebuild.

`skills/smairt-adversarial-review/SKILL.md` states "Researcher-invoked only —
never run this unprompted" **as prose with nothing enforcing it**. Both harnesses
offer a real mechanism. Folded into ticket 09.

Codex skill folders also confirm multi-file support: `scripts/`, `references/`,
`assets/`, plus required `name` + `description` frontmatter.
Source: https://github.com/openai/codex/blob/main/codex-rs/skills/src/assets/samples/skill-creator/SKILL.md
