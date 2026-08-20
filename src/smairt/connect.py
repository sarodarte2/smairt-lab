"""``smairt connect`` — harness wiring (WP4).

Tier-1/2 enforcement bridge (spec Part I, foundation 8: parity across harnesses;
foundation 2: checked mechanically). SMAIRT owns the one contract — ``AGENTS.md``
plus ``smairt check`` — and this module renders the thin, per-harness adapters
that let each assistant harness read it and run it. No harness ever defines a
SMAIRT convention; every file this module writes is generated, visible, and
deletable.

Two things every generated file does:

* Names itself as generated (a leading comment, or a ``_comment`` key where the
  format is JSON and comments are not legal), says what it does, and says that
  deleting it disables the wiring.
* Runs only read-only ``smairt`` commands (``smairt hook report`` / ``smairt
  hook gate``, thin wrappers over ``smairt check`` that speak each hook
  protocol's exit-code language) — never anything that writes.

Public entry points
--------------------
:func:`connect` — bridge + hook wiring for one harness.
:func:`connect_ci` — the GitHub Actions template (the enforcement floor).
:func:`read_strict_hooks` — reads ``smairt.yaml``'s ``settings.strict_hooks``,
used by the CLI to decide whether to also emit the pre-tool blocking hook.

Idempotency and respect for researcher edits
---------------------------------------------
Every file this module writes is compared byte-for-byte against what it would
generate on a re-run: identical content is a no-op (``skipped``); a missing
file is written (``written``); a present-but-different file is assumed to be
researcher-edited and is left untouched, with a warning naming it (``warned``).
The one exception is ``.gemini/settings.json`` (see :func:`_connect_gemini`),
which the research survey documents as a file researchers are likely to already
have populated with unrelated settings; that file is merged key-by-key instead
of compared whole — only missing keys are ever added, existing ones are never
touched, so it never actually reaches the "differs" warning path.

Judgment calls a reviewer should know about
--------------------------------------------
* Grounded vs. best-effort: five of the six configs below were verified
  against each vendor's own documentation in August 2026 —

  - Claude Code: ``.claude/settings.json`` ``{"hooks": {"<Event>":
    [{"matcher": ..., "hooks": [{"type": "command", "command": ...}]}]}}``;
    a PreToolUse hook blocks via exit code 2 (stderr goes back to the agent).
  - Codex: project-scoped ``.codex/hooks.json`` (loaded only once the project
    is trusted), same event schema as its inline ``[hooks.<Event>]`` tables in
    ``config.toml`` and deliberately Claude-shaped
    (https://learn.chatgpt.com/docs/config-file/config-advanced).
  - Cursor: ``.cursor/hooks.json`` with a required ``"version": 1``, camelCase
    event names (``stop``, ``preToolUse``), flat ``{"command": ...}`` entries,
    exit code 2 blocks (https://cursor.com/docs/hooks). Rules live in
    ``.cursor/rules/*.mdc`` with YAML frontmatter.
  - OpenCode: plugins in ``.opencode/plugins/`` export a named async function
    receiving ``{ project, client, $, directory, worktree }`` and returning a
    hooks object; ``tool.execute.before`` blocks by throwing, and
    ``session.idle`` is a real event (https://opencode.ai/docs/plugins/).
  - pi: project-local extensions in ``.pi/extensions/*.ts`` default-export a
    factory receiving ``ExtensionAPI``; a ``tool_call`` handler blocks by
    returning ``{ block: true, reason }``; ``agent_end`` fires when a run ends
    (https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/extensions.md).

  Gemini CLI remains the one best-effort config: its hook entry shape was
  never verified against a literal example, and the generated file still says
  so inside its ``_comment``.
* Exit-code adaptation: hook configs call ``smairt hook gate`` / ``smairt hook
  report`` (see ``cli.py``) rather than ``smairt check``, because the raw
  check's exit 1 means "non-blocking error" to every hook protocol above —
  only exit 2 blocks. ``gate`` exits 2 while findings exist; ``report`` always
  exits 0 so a session-end hook can never wedge a harness in a failure loop.
* Turning ``strict_hooks`` on *after* a harness has already been connected:
  for the whole-file harnesses (claude-code, codex, cursor, opencode, pi),
  the previously-written non-strict file will differ from the newly-desired
  strict file, so re-running ``connect`` reports it as "differs, left
  untouched" rather than silently upgrading it. This follows the letter of
  the idempotency rule (same content -> no-op, different content -> assume
  researcher-edited, warn) since there is no reliable way to distinguish "we
  wrote this under an older setting" from "the researcher edited this" from
  content alone. The practical fix is to delete the file and re-run connect.
  Gemini CLI does not have this limitation, because its wiring is merged
  key-by-key into one file rather than compared whole.
* ``.opencode/plugins/*.ts``, ``.pi/extensions/*.ts``, ``.cursor/rules/*.mdc``,
  and CI YAML are plain-text comparisons like the JSON hook files;
  TypeScript/Markdown/YAML comments carry the same generated-by notice JSON
  expresses via ``_comment``.
* The CI workflow content is standard GitHub Actions boilerplate (checkout +
  setup-python + ``pip install smairt`` + ``smairt check``), not sourced from
  the harness research file (CI was out of that file's scope).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml

from smairt.fsutil import write_or_warn
from smairt.project import CLAUDE_BRIDGE, Harness

# --- public result type -------------------------------------------------------


@dataclass(frozen=True)
class ConnectResult:
    """What one :func:`connect` (or :func:`connect_ci`) call did.

    Paths are project-root-relative strings, in the order they were handled.
    """

    written: tuple[str, ...]
    skipped: tuple[str, ...]
    warned: tuple[str, ...]


@dataclass
class _ResultBuilder:
    """Mutable scratchpad each harness handler appends to as it writes files.

    Exists because :class:`ConnectResult` itself is frozen (immutable) — this
    is the "in progress" version, built up one file at a time, then turned
    into the real, immutable result via :meth:`build` once the handler is done.
    """

    written: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    warned: list[str] = field(default_factory=list)

    def build(self) -> ConnectResult:
        """Freeze the scratchpad into the public, immutable :class:`ConnectResult`."""
        return ConnectResult(
            written=tuple(self.written), skipped=tuple(self.skipped), warned=tuple(self.warned)
        )


# --- shared write policy -------------------------------------------------------


def _write_or_warn(
    project_root: Path, relative: str, content: str, builder: _ResultBuilder
) -> None:
    """Write ``content`` to ``project_root / relative`` unless a differing file exists.

    This is the idempotent + respectful policy (spec WP4 constraint 4) every
    whole-file target in this module goes through, delegated to the shared
    :func:`smairt.fsutil.write_or_warn` (also used by ``smairt adopt``): identical
    content already there is a no-op; a missing file is written; a
    present-but-different file is assumed researcher-edited and left alone, with
    a warning.
    """
    status, warning = write_or_warn(project_root, relative, content)
    if status == "written":
        builder.written.append(relative)
    elif status == "skipped":
        builder.skipped.append(relative)
    else:
        assert warning is not None
        builder.warned.append(warning)


def read_strict_hooks(project_root: Path) -> bool:
    """Read ``settings.strict_hooks`` from ``smairt.yaml`` (default ``False``)."""
    path = project_root / "smairt.yaml"
    if not path.is_file():
        return False
    try:
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return False
    if not isinstance(config, dict):
        return False
    settings = config.get("settings")
    if not isinstance(settings, dict):
        return False
    return bool(settings.get("strict_hooks", False))


def _record_harness(project_root: Path, harness: Harness, builder: _ResultBuilder) -> None:
    """Append ``harness`` to ``smairt.yaml``'s ``harnesses:`` list if absent."""
    path = project_root / "smairt.yaml"
    if not path.is_file():
        return
    try:
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        builder.warned.append("smairt.yaml could not be parsed; harnesses: list left untouched.")
        return
    if not isinstance(config, dict):
        builder.warned.append("smairt.yaml is not a mapping; harnesses: list left untouched.")
        return
    harnesses = config.get("harnesses")
    if not isinstance(harnesses, list):
        harnesses = []
    if harness.value in harnesses:
        return
    harnesses.append(harness.value)
    config["harnesses"] = harnesses
    path.write_text(
        yaml.safe_dump(config, sort_keys=False, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )
    builder.written.append("smairt.yaml")


# --- Claude Code ----------------------------------------------------------------
# Verified shape: .claude/settings.json hooks, PascalCase events, entries of
# {"matcher": ..., "hooks": [{"type": "command", "command": ...}]}. A PreToolUse
# command hook blocks by exiting 2, with stderr fed back to the agent -- which is
# why the strict entry runs `smairt hook gate` (exits 2 on findings) and not
# `smairt check` (exits 1, a non-blocking error to Claude Code).


def _render_claude_settings(strict: bool) -> str:
    """Build the JSON content of ``.claude/settings.json`` (Claude Code's hook config)."""
    hooks: dict[str, Any] = {
        "Stop": [{"hooks": [{"type": "command", "command": "smairt hook report"}]}],
    }
    notice = (
        "Generated by `smairt connect claude-code`. Runs `smairt hook report` "
        "(read-only, always exits 0) when a session stops, so findings feed back "
        "before it ends."
    )
    if strict:
        hooks["PreToolUse"] = [
            {
                "matcher": "Write|Edit|MultiEdit",
                "hooks": [{"type": "command", "command": "smairt hook gate"}],
            }
        ]
        notice += (
            " Also blocks Write/Edit/MultiEdit while `smairt check` reports findings: "
            "`smairt hook gate` exits 2, Claude Code's block code "
            "(strict_hooks: true in smairt.yaml)."
        )
    notice += " Delete this file, or the smairt entries in it, to disable the wiring."
    payload = {"_comment": notice, "hooks": hooks}
    return json.dumps(payload, indent=2) + "\n"


def _connect_claude_code(project_root: Path, strict: bool, builder: _ResultBuilder) -> None:
    """Write Claude Code's two wiring files: the CLAUDE.md bridge and its hook config."""
    _write_or_warn(project_root, "CLAUDE.md", CLAUDE_BRIDGE, builder)
    _write_or_warn(project_root, ".claude/settings.json", _render_claude_settings(strict), builder)


# --- Codex ------------------------------------------------------------------
# Verified shape: project-scoped .codex/hooks.json uses the same event schema as
# the inline [hooks.<Event>] tables in config.toml -- PascalCase events (Stop,
# PreToolUse, SessionEnd, ...), entries of {"matcher": ..., "hooks": [{"type":
# "command", "command": ...}]}, deliberately mirroring Claude Code's shape.
# Codex loads a repo's .codex/ config only once the project is trusted, so the
# generated notice says so.


def _render_codex_hooks(strict: bool) -> str:
    """Build the JSON content of ``.codex/hooks.json`` (Codex's project hook config)."""
    hooks: dict[str, Any] = {
        "Stop": [{"hooks": [{"type": "command", "command": "smairt hook report"}]}]
    }
    notice = (
        "Generated by `smairt connect codex`. Runs `smairt hook report` (read-only, "
        "always exits 0) when a session stops, so findings feed back before it ends. "
        "Codex loads a project's .codex/ configuration only after you trust the "
        "project, so approve the trust prompt for this wiring to take effect."
    )
    if strict:
        hooks["PreToolUse"] = [{"hooks": [{"type": "command", "command": "smairt hook gate"}]}]
        notice += (
            " Also blocks tool calls while `smairt check` reports findings: "
            "`smairt hook gate` exits 2, the block code "
            "(strict_hooks: true in smairt.yaml)."
        )
    notice += " Delete this file to disable the wiring."
    payload = {"_comment": notice, "hooks": hooks}
    return json.dumps(payload, indent=2) + "\n"


def _connect_codex(project_root: Path, strict: bool, builder: _ResultBuilder) -> None:
    """Write Codex's one wiring file: its hook config."""
    _write_or_warn(project_root, ".codex/hooks.json", _render_codex_hooks(strict), builder)


# --- Cursor -------------------------------------------------------------------
# Verified shape: .cursor/hooks.json requires a top-level "version": 1, uses
# camelCase event names (stop, preToolUse, beforeShellExecution, ...), and flat
# {"command": ...} hook entries. A command hook blocks by exiting 2 (equivalent
# to printing {"permission": "deny"}). Cursor's native guidance channel is
# .cursor/rules/*.mdc files with YAML frontmatter, so connect also writes one
# always-applied rule pointing the agent at the AGENTS.md contract.


def _render_cursor_hooks(strict: bool) -> str:
    """Build the JSON content of ``.cursor/hooks.json`` (Cursor's hook config)."""
    hooks: dict[str, Any] = {"stop": [{"command": "smairt hook report"}]}
    notice = (
        "Generated by `smairt connect cursor`. Runs `smairt hook report` (read-only, "
        "always exits 0) when the agent session stops, so findings feed back before "
        "it ends."
    )
    if strict:
        hooks["preToolUse"] = [{"command": "smairt hook gate"}]
        notice += (
            " Also blocks tool calls while `smairt check` reports findings: "
            "`smairt hook gate` exits 2, Cursor's block code "
            "(strict_hooks: true in smairt.yaml)."
        )
    notice += " Delete this file to disable the wiring."
    payload = {"_comment": notice, "version": 1, "hooks": hooks}
    return json.dumps(payload, indent=2) + "\n"


_CURSOR_RULE = """\
---
description: SMAIRT research workspace working agreement
alwaysApply: true
---

<!-- Generated by `smairt connect cursor`. Delete this file to disable it. -->

This is a SMAIRT scientific research workspace, not a software project.

- Read `AGENTS.md` at the project root first — it is the workflow contract.
- Never `mkdir` a unit by hand: `smairt unit new stage|question` is the sole
  numbering and dating authority under `experiments/`.
- Raw logs in a unit's `logs/` are never edited once written, and every claim
  points at the log or figure that backs it.
- Run `smairt status` when you join a session; run `smairt check` before you
  end one and resolve findings.
"""


def _connect_cursor(project_root: Path, strict: bool, builder: _ResultBuilder) -> None:
    """Write Cursor's two wiring files: its hook config and its always-applied rule."""
    _write_or_warn(project_root, ".cursor/hooks.json", _render_cursor_hooks(strict), builder)
    _write_or_warn(project_root, ".cursor/rules/smairt.mdc", _CURSOR_RULE, builder)


# --- OpenCode -------------------------------------------------------------------
# Verified shape: plugins live in .opencode/plugins/ (project) as JS/TS modules
# exporting a named async function that receives { project, client, $, directory,
# worktree } and returns a hooks object. "session.idle" is a real event, and a
# `tool.execute.before` hook blocks a tool call by throwing an Error whose
# message reaches the agent. OpenCode reads AGENTS.md natively, so no bridge
# file is needed.


def _render_opencode_plugin(strict: bool) -> str:
    """Build the TypeScript source of OpenCode's plugin file (a JS/TS module, not JSON)."""
    lines = [
        "// Generated by `smairt connect opencode`. Runs `smairt hook report` (read-only,",
        "// always exits 0) when the session goes idle, so findings feed back before the",
        "// session ends.",
    ]
    if strict:
        lines.append(
            "// Also blocks tool calls while `smairt check` reports findings "
            "(strict_hooks: true in smairt.yaml)."
        )
    lines.append("// Delete this file to disable the wiring.")
    lines.append('import { execSync } from "node:child_process";')
    lines.append("")
    lines.append("export const SmairtCheck = async () => {")
    lines.append("  return {")
    lines.append("    event: async ({ event }: { event: { type: string } }) => {")
    lines.append('      if (event.type === "session.idle") {')
    lines.append("        try {")
    lines.append('          execSync("smairt hook report", { stdio: "inherit" });')
    lines.append("        } catch {")
    lines.append("          // `smairt hook report` exits 0 even with findings; this guards")
    lines.append("          // only against smairt itself being missing from PATH.")
    lines.append("        }")
    lines.append("      }")
    lines.append("    },")
    if strict:
        lines.append('    "tool.execute.before": async () => {')
        lines.append("      try {")
        lines.append('        execSync("smairt hook gate", { stdio: "ignore" });')
        lines.append("      } catch {")
        lines.append("        throw new Error(")
        lines.append(
            '          "smairt check found findings; run `smairt check` and fix them before '
            'writing further."'
        )
        lines.append("        );")
        lines.append("      }")
        lines.append("    },")
    lines.append("  };")
    lines.append("};")
    return "\n".join(lines) + "\n"


def _connect_opencode(project_root: Path, strict: bool, builder: _ResultBuilder) -> None:
    """Write OpenCode's one wiring file: its plugin module."""
    _write_or_warn(
        project_root, ".opencode/plugins/smairt-check.ts", _render_opencode_plugin(strict), builder
    )


# --- pi -------------------------------------------------------------------------
# Verified shape: project-local extensions live in .pi/extensions/*.ts (loaded
# once the project is trusted) and default-export a factory receiving
# ExtensionAPI. `agent_end` fires when an agent run ends; a `tool_call` handler
# blocks a tool call by returning { block: true, reason }. pi reads AGENTS.md
# natively, so no bridge file is needed.


def _render_pi_extension(strict: bool) -> str:
    """Build the TypeScript source of pi's extension file (a default-export factory)."""
    lines = [
        "// Generated by `smairt connect pi`. Runs `smairt hook report` (read-only,",
        "// always exits 0) when an agent run ends, so findings feed back before the",
        "// session ends.",
    ]
    if strict:
        lines.append(
            "// Also blocks edit/write tool calls while `smairt check` reports findings "
            "(strict_hooks: true in smairt.yaml)."
        )
    lines.append("// Delete this file to disable the wiring.")
    lines.append('import { execSync } from "node:child_process";')
    lines.append('import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";')
    lines.append("")
    lines.append("export default function (pi: ExtensionAPI) {")
    lines.append('  pi.on("agent_end", async () => {')
    lines.append("    try {")
    lines.append('      execSync("smairt hook report", { stdio: "inherit" });')
    lines.append("    } catch {")
    lines.append("      // `smairt hook report` exits 0 even with findings; this guards")
    lines.append("      // only against smairt itself being missing from PATH.")
    lines.append("    }")
    lines.append("  });")
    if strict:
        lines.append('  pi.on("tool_call", async (event: { toolName: string }) => {')
        lines.append('    if (event.toolName !== "edit" && event.toolName !== "write") {')
        lines.append("      return;")
        lines.append("    }")
        lines.append("    try {")
        lines.append('      execSync("smairt hook gate", { stdio: "ignore" });')
        lines.append("    } catch {")
        lines.append("      return {")
        lines.append("        block: true,")
        lines.append("        reason:")
        lines.append(
            '          "smairt check found findings; run `smairt check` and fix them before '
            'writing further.",'
        )
        lines.append("      };")
        lines.append("    }")
        lines.append("  });")
    lines.append("}")
    return "\n".join(lines) + "\n"


def _connect_pi(project_root: Path, strict: bool, builder: _ResultBuilder) -> None:
    """Write pi's one wiring file: its project-local extension."""
    _write_or_warn(
        project_root, ".pi/extensions/smairt-check.ts", _render_pi_extension(strict), builder
    )


# --- Gemini CLI -----------------------------------------------------------------
# The research file documents context.fileName as a real Gemini CLI setting (its own
# docs example already lists "AGENTS.md") and BeforeTool/SessionStart/End as real
# hook events, both in .gemini/settings.json -- but does not quote a literal hooks
# entry, so that part is BEST-EFFORT. Unlike the other four harnesses, this file is
# merged key-by-key rather than compared whole (spec WP4 step 1: "merge carefully...
# never clobber other settings"), because researchers are likely to already have a
# populated .gemini/settings.json for unrelated reasons.


def _gemini_desired_hooks(strict: bool) -> dict[str, Any]:
    """The hook entries we'd like present in Gemini CLI's settings (before merging)."""
    hooks: dict[str, Any] = {"SessionEnd": [{"command": "smairt hook report"}]}
    if strict:
        hooks["BeforeTool"] = [{"command": "smairt hook gate"}]
    return hooks


def _gemini_comment(strict: bool) -> str:
    """Build the ``_comment`` explanatory text stored inside Gemini's settings.json."""
    notice = (
        "Generated/merged by `smairt connect gemini-cli`. `context.fileName` is a "
        "documented Gemini CLI setting (its own docs use AGENTS.md as the example "
        "value) and makes Gemini CLI read AGENTS.md. BEST-EFFORT CONFIG for the hooks "
        "section: the research survey confirmed the BeforeTool/SessionEnd hook event "
        "names and that hooks live in this file, but did not capture a literal hooks "
        "entry example -- the shape below is inferred and should be verified against "
        "your Gemini CLI version. The SessionEnd hook runs `smairt hook report` "
        "(read-only, always exits 0) so findings feed back before the session ends."
    )
    if strict:
        notice += (
            " BeforeTool also blocks tool calls while `smairt check` reports findings "
            "(strict_hooks: true in smairt.yaml)."
        )
    notice += (
        " Only missing keys are ever added here -- existing settings are never "
        "overwritten. Delete the smairt entries to disable the wiring."
    )
    return notice


def _connect_gemini(project_root: Path, strict: bool, builder: _ResultBuilder) -> None:
    """Write or merge Gemini CLI's ``.gemini/settings.json``.

    Unlike every other harness handler in this module, this one does NOT go
    through :func:`_write_or_warn` (whole-file compare). Researchers likely
    already have a populated settings.json for unrelated reasons, so this
    function reads the existing JSON (if any) and adds only the keys SMAIRT
    needs that are missing — never touching a key that's already there,
    smairt's or the researcher's.
    """
    relative = ".gemini/settings.json"
    path = project_root / relative
    comment = _gemini_comment(strict)

    if not path.is_file():
        payload = {
            "_comment": comment,
            "context": {"fileName": ["AGENTS.md"]},
            "hooks": _gemini_desired_hooks(strict),
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        builder.written.append(relative)
        return

    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        builder.warned.append(f"{relative} exists and is not valid JSON; left untouched.")
        return
    if not isinstance(existing, dict):
        builder.warned.append(f"{relative} exists and is not a JSON object; left untouched.")
        return

    changed = False
    if "_comment" not in existing:
        existing["_comment"] = comment
        changed = True

    context = existing.get("context")
    if context is None:
        existing["context"] = {"fileName": ["AGENTS.md"]}
        changed = True
    elif isinstance(context, dict) and "fileName" not in context:
        context["fileName"] = ["AGENTS.md"]
        changed = True
    # else: context exists with its own fileName (or isn't a dict) -- never clobber it.

    hooks_section = existing.get("hooks")
    if hooks_section is None:
        existing["hooks"] = _gemini_desired_hooks(strict)
        changed = True
    elif isinstance(hooks_section, dict):
        for event, entries in _gemini_desired_hooks(strict).items():
            if event not in hooks_section:
                hooks_section[event] = entries
                changed = True
            # else: this event is already configured (by smairt or the researcher) --
            # leave it alone.

    if changed:
        path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
        builder.written.append(relative)
    else:
        builder.skipped.append(relative)


# --- CI template ------------------------------------------------------------------
# Standard GitHub Actions boilerplate, not sourced from the harness research file
# (CI enforcement was named as "the universal floor" there, but no template).

_CI_WORKFLOW = """\
# Generated by `smairt connect --ci`. Runs `smairt check` on every push and pull
# request -- the enforcement floor that binds every contributor and every
# harness (or none) alike, independent of local hook configuration. Delete this
# file to disable CI enforcement.
name: smairt check
on:
  push:
  pull_request:
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install smairt
      - run: smairt check
"""


def connect_ci(project_root: Path) -> ConnectResult:
    """Write the GitHub Actions template (``smairt connect --ci``)."""
    builder = _ResultBuilder()
    _write_or_warn(project_root, ".github/workflows/smairt-check.yml", _CI_WORKFLOW, builder)
    return builder.build()


# --- dispatch + public entry -------------------------------------------------------

# One entry per harness `smairt connect` knows how to wire up. Adding support
# for a new harness means writing a _connect_<name> function above (following
# the same "write file, record in builder" shape) and adding it here — see
# docs/ARCHITECTURE.md.
_HARNESS_HANDLERS: dict[Harness, Callable[[Path, bool, _ResultBuilder], None]] = {
    Harness.claude_code: _connect_claude_code,
    Harness.codex: _connect_codex,
    Harness.opencode: _connect_opencode,
    Harness.gemini_cli: _connect_gemini,
    Harness.cursor: _connect_cursor,
    Harness.pi: _connect_pi,
}


def connect(project_root: Path, harness: Harness, *, strict: bool = False) -> ConnectResult:
    """Wire ``harness`` up to this project: bridge file (where needed) + hook config.

    Idempotent and respectful of researcher edits (see module docstring). Also
    appends ``harness`` to ``smairt.yaml``'s ``harnesses:`` list if it is not
    already recorded there.
    """
    if harness is Harness.none:
        raise ValueError("harness 'none' has no wiring to install")
    handler = _HARNESS_HANDLERS[harness]
    builder = _ResultBuilder()
    handler(project_root, strict, builder)
    _record_harness(project_root, harness, builder)
    return builder.build()
