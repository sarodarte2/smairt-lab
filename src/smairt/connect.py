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
:func:`connect` — bridge + hook wiring, and skills, for one harness.
:func:`connect_ci` — the GitHub Actions template (the enforcement floor).
:func:`read_strict_hooks` — reads ``smairt.yaml``'s ``settings.strict_hooks``,
used by the CLI to decide whether to also emit the pre-tool blocking hook.

Skills delivery
----------------
Every ``_connect_<harness>`` also copies the eight ``smairt-*`` skills
(``src/smairt/assets/skills/``, read through :mod:`smairt.skills` — never a
path built from ``__file__``, which would break outside a source checkout)
into that harness's own skills surface, via the shared :func:`_install_skills`
helper. Two targets cover all six harnesses: ``.claude/skills/`` for Claude
Code, the one harness with no documented ``.agents/`` support, and
``.agents/skills/`` for the other five (Codex's *only* repo path; Gemini
CLI's higher-precedence alias; a documented location for Cursor, OpenCode,
and pi). Full findings:
``.scratch/approachable-smairt/research/03-harness-skills-delivery.md``.

**Copied, not referenced** — decisively, not by default. No harness has a
project-local "also read skills from this path" setting (Codex's
``[[skills.config]]`` disables named skills; it doesn't add search roots), so
reference is not expressible in four of six harnesses. A reference would also
resolve to a per-venv ``site-packages`` path that breaks for the second
person who clones the project. Copies drift on a ``smairt`` upgrade instead —
the accepted cost, mitigated by a provenance comment
(:func:`_skill_provenance_notice`) in every installed ``SKILL.md`` naming the
"delete the directory and re-run ``smairt connect``" remedy, inserted *after*
the closing frontmatter delimiter, never before it (Cursor and OpenCode only
recognize frontmatter that opens on line 1).

**Researcher-invoked-only, enforced, not just asserted.** Of the eight
skills, only ``smairt-adversarial-review`` says "Researcher-invoked only —
never run this unprompted" — one of this project's three anti-bias
mechanisms, alongside ``AGENTS.md``'s stakes and explanation rules. The
``disable-model-invocation: true`` frontmatter field gives that sentence a
real mechanism on the three harnesses that honor it (Claude Code, Cursor, pi)
instead of leaving it on the honor system; the other three fall back to the
prose, as they always have. Codex has its own mechanism and it is deliberately
NOT used — see the "Judgment calls" note below; see also
:data:`_RESEARCHER_INVOKED_ONLY`. The other seven skills stay model-invocable
with the plain two-field frontmatter every harness accepts unmodified —
that's the entire point of e.g. ``smairt-orient`` firing on its own.

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
* SessionStart-equivalent wiring (``smairt hook brief`` — see ``cli.py``'s
  ``hook`` command): added ONLY where the verified-shape research above
  already names the event. Claude Code's own docs confirm ``SessionStart``
  fires once at session start, so it gets the hook unconditionally (see
  :func:`_render_claude_settings`). Gemini CLI's research note above already
  lists ``SessionStart`` by name alongside ``BeforeTool``/``SessionEnd`` (only
  the literal hooks *entry shape* is best-effort there, not the event's
  existence), so it gets the hook too (see :func:`_gemini_desired_hooks`).
  Codex, Cursor, OpenCode, and pi are each verified above for a specific,
  different set of events (``Stop``/``PreToolUse``; ``stop``/``preToolUse``;
  ``session.idle``/``tool.execute.before``; ``agent_end``/``tool_call``) with
  no session-START event named anywhere in that research — so none of the
  four gets a brief hook. Guessing an event name for any of them (e.g.
  assuming Codex's ``Stop``-mirroring shape also has a ``SessionStart`` twin)
  would risk shipping a generated hook config that silently never fires,
  which is worse than the gap it would be closing.
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
* Codex skill discovery was smoke-tested by hand against a real, installed
  Codex CLI (``codex-cli 0.146.0``) before this shipped, not just source-read —
  a vendor tracker issue (https://github.com/openai/codex/issues/16012)
  reports repo-local ``.agents/skills`` not being injected into a session even
  though ``codex-rs/core-skills/src/loader.rs`` implements exactly that
  discovery. **Confirmed working**: ``codex debug prompt-input`` (renders the
  model-visible prompt without needing a live model call) showed a skill
  dropped into a throwaway project's ``.agents/skills/<name>/SKILL.md`` listed
  in the injected ``<skills_instructions>`` block by name, description, and
  file path — codex#16012 does not reproduce here.
* **Codex's ``agents/openai.yaml`` policy file is deliberately not written.**
  It is the documented way to stop Codex auto-selecting a skill
  (``policy: allow_implicit_invocation: false``, per
  https://learn.chatgpt.com/docs/build-skills) and would be the natural Codex
  counterpart to ``disable-model-invocation``. Measured against
  ``codex-cli 0.146.0``, it does something else: the skill disappears from the
  injected list **entirely**, so it cannot be invoked explicitly either.
  Isolated by bisection — an ``agents/openai.yaml`` carrying only an
  ``interface:`` block leaves the skill visible; adding ``policy:``, alone or
  alongside ``interface:``, is what makes it vanish. ``smairt-adversarial-review``
  has no mode of use *except* explicit researcher invocation, so on Codex that
  file would not constrain the skill, it would delete it — trading a working
  anti-bias mechanism for no mechanism at all. Codex therefore falls back to
  the SKILL.md prose, exactly like Gemini CLI and OpenCode. Revisit if a
  future Codex release makes the documented behavior real.
* Scoping guarantee: every file this module writes lands under the project
  root it was given — never ``$HOME`` or a harness's global config file (e.g.
  ``~/.claude/settings.json``, ``~/.cursor/hooks.json``). This is enforced,
  not just promised: :func:`_write_or_warn` below rejects any ``relative``
  that is absolute or that resolves outside ``project_root`` before it ever
  reaches disk. It is also *stated*, in every generated file's own notice —
  see :data:`_SCOPE_NOTE` — so a researcher reading the file (not this
  module's source) still sees the guarantee spelled out.
* Broken ``smairt.yaml`` degrade policy (DG-1): :func:`read_strict_hooks` and
  :func:`_record_harness` both read the file through
  :func:`smairt.project.read_project_config` and silently fall back to their
  safe default if it can't be read as a mapping, rather than each printing
  its own warning (which is what these two functions used to disagree about
  — see :mod:`smairt.check`'s "Judgment calls" section for the full policy
  and why silent-here is actually the safe choice, not a regression).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml

from smairt import __version__
from smairt.fsutil import write_or_warn
from smairt.project import CLAUDE_BRIDGE, Harness, read_project_config
from smairt.skills import list_skills, read_skill

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


# --- shared notice text ---------------------------------------------------------
#
# Every renderer below assembles a "what this file is / does / how to undo it"
# notice by hand (there is no template engine — see the module docstring's
# "Where generated text lives" analogue in docs/ARCHITECTURE.md). The pieces
# below exist only because six near-identical sentences were previously typed
# out six times; each helper still takes the harness-specific words as
# arguments rather than hiding them, so nothing that used to vary loses its
# voice (Codex's trust caveat, Claude's "or the smairt entries in it", each
# harness's own trigger phrasing, ...).

_HOOK_REPORT = "smairt hook report"
_HOOK_GATE = "smairt hook gate"
_HOOK_BRIEF = "smairt hook brief"

_SCOPE_NOTE = (
    "Project-scoped: affects only sessions opened inside this project, never "
    "your harness's global configuration."
)
"""The one sentence every generated file's notice repeats, verbatim.

States in the file itself the guarantee :func:`_write_or_warn` enforces on the
way to disk (see the module docstring's "Scoping guarantee" bullet): a
researcher who opens the generated file — not this module's source — should
still be able to see that it can only ever affect this project.
"""

_DELETE_FILE_NOTICE = "Delete this file to disable the wiring."
"""The plain "how to undo this" sentence shared by every harness except Claude
Code, whose own wording ("... or the smairt entries in it ...") reflects that
``.claude/settings.json`` is a file Claude Code also uses for unrelated
settings, unlike the other harnesses' smairt-only files.
"""


def _report_notice(trigger: str) -> str:
    """The "runs report on trigger" sentence shared by claude-code/codex/cursor's JSON notices.

    ``trigger`` is the harness-specific "when ..." clause (e.g. "a session
    stops", "the agent session stops") — the one part of this sentence that
    genuinely differs per harness.
    """
    return (
        f"Runs `{_HOOK_REPORT}` (read-only, always exits 0) when {trigger}, so "
        "findings feed back before it ends."
    )


def _brief_notice(trigger: str) -> str:
    """The "runs brief on trigger" sentence for a harness's SessionStart-equivalent notice.

    Mirrors :func:`_report_notice`'s shape exactly (same "read-only, always
    exits 0" promise, same one-varying-clause parameter) because ``smairt
    hook brief`` makes the identical never-wedge-the-session guarantee
    ``smairt hook report`` does — see ``cli.py``'s ``hook`` command docstring.
    The two only differ in WHAT they print (``smairt status``'s human view vs.
    `smairt check`'s findings) and WHEN they fire (session start vs. session
    end) — this exists as a separate function, not a second call to
    :func:`_report_notice` with a swapped command name, so the "why" half of
    the sentence (orienting a fresh session on its own, unprompted) stays
    specific to brief rather than reusing report's "findings feed back before
    it ends" phrasing, which would be actively wrong for a hook that runs at
    the START of a session.
    """
    return (
        f"Runs `{_HOOK_BRIEF}` (read-only, always exits 0) when {trigger}, so a "
        "fresh session orients itself (`smairt status`'s view) without the "
        "researcher having to ask."
    )


def _gate_notice(what: str, whose: str) -> str:
    """The strict-mode "also blocks ..." sentence shared by claude-code/codex/cursor's JSON notices.

    ``what`` is what gets blocked (e.g. "Write/Edit/MultiEdit", "tool calls");
    ``whose`` names whose block code exit 2 is (e.g. "Claude Code's", "the",
    "Cursor's") — both genuinely harness-specific, so both stay parameters
    rather than getting flattened away.
    """
    return (
        f" Also blocks {what} while `smairt check` reports findings: "
        f"`{_HOOK_GATE}` exits 2, {whose} block code (strict_hooks: true in smairt.yaml)."
    )


def _ts_header(command_name: str, trigger: str) -> list[str]:
    """The three-line leading ``//`` comment shared by OpenCode's and pi's TS notices.

    ``command_name`` is the ``smairt connect <name>`` invocation; ``trigger``
    is the harness-specific "when ..." clause (e.g. "the session goes idle",
    "an agent run ends").
    """
    return [
        f"// Generated by `smairt connect {command_name}`. Runs `{_HOOK_REPORT}` (read-only,",
        f"// always exits 0) when {trigger}, so findings feed back before the",
        "// session ends.",
    ]


def _ts_strict_notice(what: str) -> str:
    """The strict-mode "also blocks ..." comment line shared by OpenCode's and pi's TS notices.

    ``what`` is what gets blocked (e.g. "tool calls", "edit/write tool
    calls") — genuinely harness-specific.
    """
    return (
        f"// Also blocks {what} while `smairt check` reports findings "
        "(strict_hooks: true in smairt.yaml)."
    )


# --- shared write policy -------------------------------------------------------


def _guard_project_scoped(project_root: Path, relative: str) -> None:
    """Raise if writing to ``relative`` would land outside ``project_root``.

    A programmer-error guard, not a user-facing check: every ``relative``
    passed into this module is a string literal a few lines above its call
    site (see the ``_connect_*`` handlers below), never anything derived from
    user input, so tripping this should only happen if a future edit
    introduces a typo'd ``../`` or an absolute path. It exists to make the
    scoping guarantee described in the module docstring mechanically
    enforced rather than merely promised — see :data:`_SCOPE_NOTE`.
    """
    candidate = Path(relative)
    if candidate.is_absolute():
        raise ValueError(
            f"connect.py refuses to write outside the project: relative path "
            f"{relative!r} is absolute."
        )
    resolved_root = project_root.resolve()
    resolved_target = (project_root / candidate).resolve()
    if not resolved_target.is_relative_to(resolved_root):
        raise ValueError(
            f"connect.py refuses to write outside the project: {relative!r} "
            f"resolves to {resolved_target}, which escapes {resolved_root}."
        )


def _write_or_warn(
    project_root: Path, relative: str, content: str, builder: _ResultBuilder
) -> None:
    """Write ``content`` to ``project_root / relative`` unless a differing file exists.

    This is the idempotent + respectful policy (spec WP4 constraint 4) every
    whole-file target in this module goes through, delegated to the shared
    :func:`smairt.fsutil.write_or_warn` (also used by ``smairt adopt``): identical
    content already there is a no-op; a missing file is written; a
    present-but-different file is assumed researcher-edited and left alone, with
    a warning. :func:`_guard_project_scoped` runs first so nothing this module
    writes can ever land outside ``project_root``.
    """
    _guard_project_scoped(project_root, relative)
    status, warning = write_or_warn(project_root, relative, content)
    if status == "written":
        builder.written.append(relative)
    elif status == "skipped":
        builder.skipped.append(relative)
    else:
        assert warning is not None
        builder.warned.append(warning)


def read_strict_hooks(project_root: Path) -> bool:
    """Read ``settings.strict_hooks`` from ``smairt.yaml`` (default ``False``).

    Goes through :func:`smairt.project.read_project_config` and falls back to
    ``False`` -- silently, by design -- if ``smairt.yaml`` can't be read as a
    mapping at all. This is DG-1's degrade policy, not an oversight: a YAML
    SYNTAX error already stops every command (including the one that calls
    this, ``smairt connect``) before this function ever runs, at
    :func:`smairt.project.find_project_root`'s fail-fast; a file that parses
    but is the wrong shape is rule SMAIRT011's job to surface, the next time
    `smairt check` runs. See :mod:`smairt.check`'s "Judgment calls" section
    for the full policy this and :func:`_record_harness` below both follow.
    """
    config = read_project_config(project_root)
    if config.data is None:
        return False
    settings = config.data.get("settings")
    if not isinstance(settings, dict):
        return False
    return bool(settings.get("strict_hooks", False))


def _record_harness(project_root: Path, harness: Harness, builder: _ResultBuilder) -> None:
    """Append ``harness`` to ``smairt.yaml``'s ``harnesses:`` list if absent.

    Warns, rather than failing or staying quiet, when ``smairt.yaml`` cannot
    be read as a mapping. The one DG-1 policy this module follows draws its
    line at reads versus writes, not at call sites: a *read* that can fall
    back to a documented safe default does so silently (see
    :func:`read_strict_hooks`, which falls back to non-strict), because
    nothing the researcher asked for has gone missing. This is a *write* --
    the researcher ran ``smairt connect`` and asked for this harness to be
    recorded. Skipping that silently would let the command report every file
    it wrote and exit 0 while the harness never made it into the project's
    identity file, and the researcher would only learn that from a later
    ``smairt check``. A write that did not happen is always worth saying out
    loud. See :mod:`smairt.check`'s "Judgment calls" section.
    """
    config = read_project_config(project_root)
    if config.data is None:
        builder.warned.append(
            "smairt.yaml could not be read as a mapping, so this harness was not added to its "
            "harnesses: list -- the wiring files above were still written. Run `smairt check` "
            "to see what is wrong with smairt.yaml, then re-run this command."
        )
        return
    harnesses = config.data.get("harnesses")
    if not isinstance(harnesses, list):
        harnesses = []
    if harness.value in harnesses:
        return
    harnesses.append(harness.value)
    config.data["harnesses"] = harnesses
    (project_root / "smairt.yaml").write_text(
        yaml.safe_dump(config.data, sort_keys=False, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )
    builder.written.append("smairt.yaml")


# --- Skills -----------------------------------------------------------------------
# Verified shape: every harness converged on directory-per-skill + a SKILL.md with
# YAML frontmatter -- the Agent Skills open standard (agentskills.io). Two
# project-local paths reach all six: .claude/skills/<name>/SKILL.md for Claude
# Code (the one harness whose docs enumerate skill locations without .agents/),
# and .agents/skills/<name>/SKILL.md for the other five -- Codex's *only* repo
# path, Gemini CLI's higher-precedence alias, and a documented location for
# Cursor, OpenCode, and pi. Full findings and per-harness sources:
# .scratch/approachable-smairt/research/03-harness-skills-delivery.md.

_SKILLS_ROOT_CLAUDE = ".claude/skills"
_SKILLS_ROOT_SHARED = ".agents/skills"
"""The two skill-install targets. Not a per-harness dict, on purpose: keeping
just these two names makes it obvious in every call site below which of the
two shapes a harness gets, and keeps `_install_skills` itself harness-blind --
it only ever sees "claude" or "shared", never which of the five shared-target
harnesses triggered the write. That matters for idempotency: nothing about the
rendered bytes may depend on which harness wrote them, or the second harness
connected to the same project would see a spurious "differs" warning instead
of the free `skipped` the module docstring promises.
"""

_RESEARCHER_INVOKED_ONLY = frozenset({"smairt-adversarial-review"})
"""Skills that must never fire without the researcher explicitly asking for them.

This is one of the project's three anti-bias mechanisms, alongside AGENTS.md's
stakes rule and explanation rule -- and until now it has rested entirely on
prose: `smairt-adversarial-review`'s own SKILL.md says "Researcher-invoked
only -- never run this unprompted" with nothing enforcing it. Three harnesses
can actually enforce it -- Claude Code, Cursor, and pi, via the
``disable-model-invocation`` frontmatter field :func:`_render_skill_md` adds
below. The rest fall back to the prose, same as before; Codex's own mechanism
would remove the skill outright on the version tested, so it is deliberately
not used (see the module docstring's "Judgment calls"). The other seven
shipped skills are meant to fire on their own -- that's the entire point of
`smairt-orient` running "always", or `smairt-new-question` catching a probe
before it starts -- so this set has exactly one member, not eight.
"""


def _split_frontmatter(skill_md: str) -> tuple[str, str]:
    """Split a skill's Markdown into ``(frontmatter incl. trailing "---\\n", rest)``.

    Looks for the closing ``---`` on its own line rather than assuming a fixed
    line count, so this keeps working if a skill's frontmatter grows a field.
    Every shipped skill starts with a frontmatter block (asserted by
    ``tests/test_skills.py``), so a skill missing the closing delimiter would
    be a packaging bug, not a normal input -- hence the plain ``ValueError``
    rather than a quieter fallback.
    """
    lines = skill_md.splitlines(keepends=True)
    for i in range(1, len(lines)):
        if lines[i].rstrip("\n") == "---":
            return "".join(lines[: i + 1]), "".join(lines[i + 1 :])
    raise ValueError("skill Markdown has no closing '---' frontmatter delimiter")


def _skill_provenance_notice(root: str) -> str:
    """The "this is a copy, here's how to refresh it" comment every installed skill carries.

    Never names a specific harness for :data:`_SKILLS_ROOT_SHARED`: doing so
    would make the same skill's rendered bytes differ depending on which
    harness happened to write them first, breaking the free idempotency the
    shared target is supposed to get (see the module docstring's "Skills
    delivery" section). Claude Code's copy is the one harness-specific
    exception, since :data:`_SKILLS_ROOT_CLAUDE` is only ever written by
    :func:`_connect_claude_code`.
    """
    command = (
        "smairt connect claude-code" if root == _SKILLS_ROOT_CLAUDE else "smairt connect <harness>"
    )
    return (
        f"<!-- Copied by `{command}` from the skill smairt {__version__} ships --\n"
        "     not referenced, so it goes stale the next time smairt is upgraded.\n"
        "     If you edited this file on purpose, ignore this notice. If you\n"
        f"     didn't, delete this skill's directory and re-run `{command}` to\n"
        "     reinstall the version smairt currently ships. -->"
    )


def _render_skill_md(root: str, name: str, body: str) -> str:
    """Render one shipped skill's ``SKILL.md`` (:func:`smairt.skills.read_skill`) for ``root``.

    Two things ever differ from the shipped bytes:

    * The provenance notice above is always inserted right after the closing
      frontmatter delimiter, never before the opening one -- Cursor and
      OpenCode only recognize frontmatter that starts on the file's first
      line, so prepending anything would silently break the skill everywhere
      but Claude Code.
    * For :data:`_RESEARCHER_INVOKED_ONLY` skills, ``disable-model-invocation:
      true`` is inserted into the frontmatter itself. Claude Code, Cursor, and
      pi all honor that field (per the harness research); it's simply an
      unrecognized key everywhere else -- OpenCode's frontmatter parser is a
      documented closed set that ignores unknown keys rather than rejecting
      them, and neither Codex nor Gemini CLI's docs describe rejecting extra
      frontmatter either. So this is a real enforcement mechanism on three
      harnesses and a no-op, not a break, on the rest.
    """
    frontmatter, rest = _split_frontmatter(body)
    if name in _RESEARCHER_INVOKED_ONLY:
        frontmatter = frontmatter[: -len("---\n")] + "disable-model-invocation: true\n---\n"
    return f"{frontmatter}\n{_skill_provenance_notice(root)}\n{rest}"


def _install_skills(project_root: Path, root: str, builder: _ResultBuilder) -> None:
    """Copy every skill smairt ships into ``root``, one ``<name>/SKILL.md`` at a time.

    Copy, not reference (see the module docstring's "Skills delivery"
    section): no harness has a project-local "also read skills from this
    path" setting, and a reference would resolve to a per-venv
    ``site-packages`` path that breaks for the second person who clones the
    project. Goes through :func:`smairt.skills.list_skills` /
    :func:`smairt.skills.read_skill` -- never a path built from ``__file__``
    -- so this keeps working whether ``smairt`` is running from a wheel, an
    editable install, or a zip.
    """
    for name in list_skills():
        rendered = _render_skill_md(root, name, read_skill(name))
        _write_or_warn(project_root, f"{root}/{name}/SKILL.md", rendered, builder)


# --- Claude Code ----------------------------------------------------------------
# Verified shape: .claude/settings.json hooks, PascalCase events, entries of
# {"matcher": ..., "hooks": [{"type": "command", "command": ...}]}. A PreToolUse
# command hook blocks by exiting 2, with stderr fed back to the agent -- which is
# why the strict entry runs `smairt hook gate` (exits 2 on findings) and not
# `smairt check` (exits 1, a non-blocking error to Claude Code). SessionStart is
# a confirmed Claude Code event too (fires once at the start of a session), which
# is what lets `smairt hook brief` run there unconditionally, the same way `Stop`
# always runs `smairt hook report`.


def _render_claude_settings(strict: bool) -> str:
    """Build the JSON content of ``.claude/settings.json`` (Claude Code's hook config).

    ``SessionStart`` runs ``smairt hook brief`` unconditionally (not gated by
    ``strict``, same as ``Stop``'s ``smairt hook report`` below) — this is a
    read-only orientation aid, not an enforcement mechanism, so there is no
    "strict" variant of it to gate. It exists to fix a specific gap: a fresh
    assistant session in a SMAIRT project previously had no signal to orient
    itself (``smairt status``'s view) unless the researcher thought to ask
    for it, which is exactly the failure this hook closes — see
    :func:`smairt.status.build_status_report` for what it prints.
    """
    hooks: dict[str, Any] = {
        "SessionStart": [{"hooks": [{"type": "command", "command": _HOOK_BRIEF}]}],
        "Stop": [{"hooks": [{"type": "command", "command": _HOOK_REPORT}]}],
    }
    notice = (
        "Generated by `smairt connect claude-code`. "
        + _brief_notice("a session starts")
        + " "
        + _report_notice("a session stops")
    )
    if strict:
        hooks["PreToolUse"] = [
            {
                "matcher": "Write|Edit|MultiEdit",
                "hooks": [{"type": "command", "command": _HOOK_GATE}],
            }
        ]
        notice += _gate_notice("Write/Edit/MultiEdit", "Claude Code's")
    notice += (
        f" {_SCOPE_NOTE} Delete this file, or the smairt entries in it, to disable the wiring."
    )
    payload = {"_comment": notice, "hooks": hooks}
    return json.dumps(payload, indent=2) + "\n"


def _connect_claude_code(project_root: Path, strict: bool, builder: _ResultBuilder) -> None:
    """Write Claude Code's wiring: the CLAUDE.md bridge, its hook config, and its skills."""
    _write_or_warn(project_root, "CLAUDE.md", CLAUDE_BRIDGE, builder)
    _write_or_warn(project_root, ".claude/settings.json", _render_claude_settings(strict), builder)
    _install_skills(project_root, _SKILLS_ROOT_CLAUDE, builder)


# --- Codex ------------------------------------------------------------------
# Verified shape: project-scoped .codex/hooks.json uses the same event schema as
# the inline [hooks.<Event>] tables in config.toml -- PascalCase events (Stop,
# PreToolUse, SessionEnd, ...), entries of {"matcher": ..., "hooks": [{"type":
# "command", "command": ...}]}, deliberately mirroring Claude Code's shape.
# Codex loads a repo's .codex/ config only once the project is trusted, so the
# generated notice says so.


def _render_codex_hooks(strict: bool) -> str:
    """Build the JSON content of ``.codex/hooks.json`` (Codex's project hook config)."""
    hooks: dict[str, Any] = {"Stop": [{"hooks": [{"type": "command", "command": _HOOK_REPORT}]}]}
    notice = (
        "Generated by `smairt connect codex`. "
        + _report_notice("a session stops")
        + " Codex loads a project's .codex/ configuration only after you trust the "
        "project, so approve the trust prompt for this wiring to take effect."
    )
    if strict:
        hooks["PreToolUse"] = [{"hooks": [{"type": "command", "command": _HOOK_GATE}]}]
        notice += _gate_notice("tool calls", "the")
    notice += f" {_SCOPE_NOTE} {_DELETE_FILE_NOTICE}"
    payload = {"_comment": notice, "hooks": hooks}
    return json.dumps(payload, indent=2) + "\n"


def _connect_codex(project_root: Path, strict: bool, builder: _ResultBuilder) -> None:
    """Write Codex's hook config, plus its (shared) copy of smairt's skills."""
    _write_or_warn(project_root, ".codex/hooks.json", _render_codex_hooks(strict), builder)
    _install_skills(project_root, _SKILLS_ROOT_SHARED, builder)


# --- Cursor -------------------------------------------------------------------
# Verified shape: .cursor/hooks.json requires a top-level "version": 1, uses
# camelCase event names (stop, preToolUse, beforeShellExecution, ...), and flat
# {"command": ...} hook entries. A command hook blocks by exiting 2 (equivalent
# to printing {"permission": "deny"}). Cursor's native guidance channel is
# .cursor/rules/*.mdc files with YAML frontmatter, so connect also writes one
# always-applied rule pointing the agent at the AGENTS.md contract.


def _render_cursor_hooks(strict: bool) -> str:
    """Build the JSON content of ``.cursor/hooks.json`` (Cursor's hook config)."""
    hooks: dict[str, Any] = {"stop": [{"command": _HOOK_REPORT}]}
    notice = "Generated by `smairt connect cursor`. " + _report_notice("the agent session stops")
    if strict:
        hooks["preToolUse"] = [{"command": _HOOK_GATE}]
        notice += _gate_notice("tool calls", "Cursor's")
    notice += f" {_SCOPE_NOTE} {_DELETE_FILE_NOTICE}"
    payload = {"_comment": notice, "version": 1, "hooks": hooks}
    return json.dumps(payload, indent=2) + "\n"


_CURSOR_RULE = f"""\
---
description: SMAIRT research workspace working agreement
alwaysApply: true
---

<!-- Generated by `smairt connect cursor`. {_SCOPE_NOTE} Delete this file to
     disable it. -->

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
    """Write Cursor's hook config, its always-applied rule, and its (shared) skills copy."""
    _write_or_warn(project_root, ".cursor/hooks.json", _render_cursor_hooks(strict), builder)
    _write_or_warn(project_root, ".cursor/rules/smairt.mdc", _CURSOR_RULE, builder)
    _install_skills(project_root, _SKILLS_ROOT_SHARED, builder)


# --- OpenCode -------------------------------------------------------------------
# Verified shape: plugins live in .opencode/plugins/ (project) as JS/TS modules
# exporting a named async function that receives { project, client, $, directory,
# worktree } and returns a hooks object. "session.idle" is a real event, and a
# `tool.execute.before` hook blocks a tool call by throwing an Error whose
# message reaches the agent. OpenCode reads AGENTS.md natively, so no bridge
# file is needed.


def _render_opencode_plugin(strict: bool) -> str:
    """Build the TypeScript source of OpenCode's plugin file (a JS/TS module, not JSON)."""
    lines = _ts_header("opencode", "the session goes idle")
    if strict:
        lines.append(_ts_strict_notice("tool calls"))
    lines.append(f"// {_SCOPE_NOTE}")
    lines.append("// Delete this file to disable the wiring.")
    lines.append('import { execSync } from "node:child_process";')
    lines.append("")
    lines.append("export const SmairtCheck = async () => {")
    lines.append("  return {")
    lines.append("    event: async ({ event }: { event: { type: string } }) => {")
    lines.append('      if (event.type === "session.idle") {')
    lines.append("        try {")
    lines.append(f'          execSync("{_HOOK_REPORT}", {{ stdio: "inherit" }});')
    lines.append("        } catch {")
    lines.append(f"          // `{_HOOK_REPORT}` exits 0 even with findings; this guards")
    lines.append("          // only against smairt itself being missing from PATH.")
    lines.append("        }")
    lines.append("      }")
    lines.append("    },")
    if strict:
        lines.append('    "tool.execute.before": async () => {')
        lines.append("      try {")
        lines.append(f'        execSync("{_HOOK_GATE}", {{ stdio: "ignore" }});')
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
    """Write OpenCode's plugin module, plus its (shared) copy of smairt's skills."""
    _write_or_warn(
        project_root, ".opencode/plugins/smairt-check.ts", _render_opencode_plugin(strict), builder
    )
    _install_skills(project_root, _SKILLS_ROOT_SHARED, builder)


# --- pi -------------------------------------------------------------------------
# Verified shape: project-local extensions live in .pi/extensions/*.ts (loaded
# once the project is trusted) and default-export a factory receiving
# ExtensionAPI. `agent_end` fires when an agent run ends; a `tool_call` handler
# blocks a tool call by returning { block: true, reason }. pi reads AGENTS.md
# natively, so no bridge file is needed.


def _render_pi_extension(strict: bool) -> str:
    """Build the TypeScript source of pi's extension file (a default-export factory)."""
    lines = _ts_header("pi", "an agent run ends")
    if strict:
        lines.append(_ts_strict_notice("edit/write tool calls"))
    lines.append(f"// {_SCOPE_NOTE}")
    lines.append("// Delete this file to disable the wiring.")
    lines.append('import { execSync } from "node:child_process";')
    lines.append('import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";')
    lines.append("")
    lines.append("export default function (pi: ExtensionAPI) {")
    lines.append('  pi.on("agent_end", async () => {')
    lines.append("    try {")
    lines.append(f'      execSync("{_HOOK_REPORT}", {{ stdio: "inherit" }});')
    lines.append("    } catch {")
    lines.append(f"      // `{_HOOK_REPORT}` exits 0 even with findings; this guards")
    lines.append("      // only against smairt itself being missing from PATH.")
    lines.append("    }")
    lines.append("  });")
    if strict:
        lines.append('  pi.on("tool_call", async (event: { toolName: string }) => {')
        lines.append('    if (event.toolName !== "edit" && event.toolName !== "write") {')
        lines.append("      return;")
        lines.append("    }")
        lines.append("    try {")
        lines.append(f'      execSync("{_HOOK_GATE}", {{ stdio: "ignore" }});')
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
    """Write pi's project-local extension, plus its (shared) copy of smairt's skills."""
    _write_or_warn(
        project_root, ".pi/extensions/smairt-check.ts", _render_pi_extension(strict), builder
    )
    _install_skills(project_root, _SKILLS_ROOT_SHARED, builder)


# --- Gemini CLI -----------------------------------------------------------------
# The research file documents context.fileName as a real Gemini CLI setting (its own
# docs example already lists "AGENTS.md") and BeforeTool/SessionStart/End as real
# hook events, both in .gemini/settings.json -- but does not quote a literal hooks
# entry, so that part is BEST-EFFORT. Unlike the other four harnesses, this file is
# merged key-by-key rather than compared whole (spec WP4 step 1: "merge carefully...
# never clobber other settings"), because researchers are likely to already have a
# populated .gemini/settings.json for unrelated reasons.


def _gemini_desired_hooks(strict: bool) -> dict[str, Any]:
    """The hook entries we'd like present in Gemini CLI's settings (before merging).

    ``SessionStart`` is included unconditionally, same as Claude Code's (see
    :func:`_render_claude_settings`): the section header comment above already
    establishes ``SessionStart`` as a real, documented Gemini CLI event name
    (alongside ``BeforeTool``/``SessionEnd``), so wiring it here is not a guess
    the way an unlisted event name would be -- only the exact entry SHAPE below
    is best-effort, not the event's existence. It runs `smairt hook brief`,
    read-only and always exit-0, for the identical reason Claude Code's does:
    orienting a fresh session without the researcher having to ask.
    """
    hooks: dict[str, Any] = {
        "SessionStart": [{"command": _HOOK_BRIEF}],
        "SessionEnd": [{"command": _HOOK_REPORT}],
    }
    if strict:
        hooks["BeforeTool"] = [{"command": _HOOK_GATE}]
    return hooks


def _gemini_comment(strict: bool) -> str:
    """Build the ``_comment`` explanatory text stored inside Gemini's settings.json."""
    notice = (
        "Generated/merged by `smairt connect gemini-cli`. `context.fileName` is a "
        "documented Gemini CLI setting (its own docs use AGENTS.md as the example "
        "value) and makes Gemini CLI read AGENTS.md. BEST-EFFORT CONFIG for the hooks "
        "section: the research survey confirmed the BeforeTool/SessionStart/SessionEnd "
        "hook event names and that hooks live in this file, but did not capture a "
        "literal hooks entry example -- the shape below is inferred and should be "
        f"verified against your Gemini CLI version. The SessionStart hook runs "
        f"`{_HOOK_BRIEF}` (read-only, always exits 0) so a fresh session orients itself; "
        f"the SessionEnd hook runs `{_HOOK_REPORT}` (read-only, always exits 0) so "
        "findings feed back before the session ends."
    )
    if strict:
        notice += (
            " BeforeTool also blocks tool calls while `smairt check` reports findings "
            "(strict_hooks: true in smairt.yaml)."
        )
    notice += (
        " Only missing keys are ever added here -- existing settings are never "
        f"overwritten. {_SCOPE_NOTE} Delete the smairt entries to disable the wiring."
    )
    return notice


def _connect_gemini(project_root: Path, strict: bool, builder: _ResultBuilder) -> None:
    """Write or merge Gemini CLI's ``.gemini/settings.json``.

    Unlike every other harness handler in this module, this one does NOT go
    through :func:`_write_or_warn` (whole-file compare). Researchers likely
    already have a populated settings.json for unrelated reasons, so this
    function reads the existing JSON (if any) and adds only the keys SMAIRT
    needs that are missing — never touching a key that's already there,
    smairt's or the researcher's. Skill installation (its own (shared) copy
    of smairt's skills) runs first and unconditionally, since it's unrelated
    to whichever of settings.json's several early-return branches below fires.
    """
    _install_skills(project_root, _SKILLS_ROOT_SHARED, builder)
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

_CI_WORKFLOW = f"""\
# Generated by `smairt connect --ci`. Runs `smairt check` on every push and pull
# request -- the enforcement floor that binds every contributor and every
# harness (or none) alike, independent of local hook configuration.
# {_SCOPE_NOTE}
# Delete this file to disable CI enforcement.
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
