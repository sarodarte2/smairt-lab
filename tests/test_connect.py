"""Tests for ``smairt connect`` (src/smairt/connect.py): per-harness hook + skills wiring.

One section per harness (Claude Code, Codex, Cursor, OpenCode, Gemini CLI, pi)
plus the CI template and the shared idempotency/strict-mode behavior. Checks
what gets written, that re-running is a no-op, and that an edited file is
left alone with a warning rather than overwritten. A dedicated "skills"
section covers the two-path dispatch (``.claude/skills/`` vs the shared
``.agents/skills/``), the provenance notice, ``disable-model-invocation``
enforcement for ``smairt-adversarial-review``, and the free idempotency the
shared target gets when a second harness is connected.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from smairt import connect as connect_module
from smairt.cli import app
from smairt.project import Harness, create_project
from smairt.skills import list_skills

runner = CliRunner()


def _project(tmp_path: Path, harness: Harness = Harness.none) -> Path:
    root = tmp_path / "project"
    create_project(
        root,
        name="Connect Test Project",
        researcher="Ada Lovelace",
        description="Exercises smairt connect.",
        harness=harness,
        created=date(2026, 1, 1),
        scaffold_version="0.0.0-test",
    )
    return root


def _skill_files(root: str) -> tuple[str, ...]:
    """The exact file list ``_install_skills`` writes under ``root``, in order.

    Mirrors ``connect_module._install_skills`` rather than hardcoding the
    eight names, so this stays correct if a skill is added or removed. One
    ``SKILL.md`` per skill and nothing else -- no harness gets a sidecar file.
    """
    return tuple(f"{root}/{name}/SKILL.md" for name in list_skills())


# --- claude-code ----------------------------------------------------------------


def test_claude_code_writes_bridge_and_stop_hook(tmp_path: Path) -> None:
    root = _project(tmp_path)

    result = connect_module.connect(root, Harness.claude_code, strict=False)

    assert "CLAUDE.md" in result.skipped  # create_project already wrote the bridge
    assert ".claude/settings.json" in result.written
    payload = json.loads((root / ".claude" / "settings.json").read_text())
    assert "_comment" in payload
    assert payload["hooks"]["Stop"][0]["hooks"][0]["command"] == "smairt hook report"
    assert "PreToolUse" not in payload["hooks"]


def test_claude_code_creates_bridge_when_missing(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "CLAUDE.md").unlink()

    result = connect_module.connect(root, Harness.claude_code, strict=False)

    assert "CLAUDE.md" in result.written
    assert (root / "CLAUDE.md").read_text() == "# SMAIRT\n@AGENTS.md\n"


def test_claude_code_second_run_is_a_no_op(tmp_path: Path) -> None:
    root = _project(tmp_path)
    connect_module.connect(root, Harness.claude_code, strict=False)

    result = connect_module.connect(root, Harness.claude_code, strict=False)

    assert result.written == ()
    assert set(result.skipped) == {"CLAUDE.md", ".claude/settings.json"} | set(
        _skill_files(connect_module._SKILLS_ROOT_CLAUDE)
    )
    assert result.warned == ()


def test_claude_code_strict_hooks_adds_pre_tool_use_blocking_config(tmp_path: Path) -> None:
    root = _project(tmp_path)

    connect_module.connect(root, Harness.claude_code, strict=True)

    payload = json.loads((root / ".claude" / "settings.json").read_text())
    pre_tool_use = payload["hooks"]["PreToolUse"][0]
    assert pre_tool_use["hooks"][0]["command"] == "smairt hook gate"
    assert "matcher" in pre_tool_use


def test_claude_code_never_touches_a_researcher_edited_hook_file(tmp_path: Path) -> None:
    root = _project(tmp_path)
    settings_dir = root / ".claude"
    settings_dir.mkdir()
    custom = json.dumps(
        {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo hi"}]}]}}
    )
    (settings_dir / "settings.json").write_text(custom, encoding="utf-8")

    result = connect_module.connect(root, Harness.claude_code, strict=False)

    assert (settings_dir / "settings.json").read_text() == custom
    assert any(".claude/settings.json" in warning for warning in result.warned)
    assert ".claude/settings.json" not in result.written


def test_claude_code_never_overwrites_a_researcher_edited_bridge(tmp_path: Path) -> None:
    root = _project(tmp_path)
    custom_bridge = "# My own bridge\n@AGENTS.md\nExtra notes.\n"
    (root / "CLAUDE.md").write_text(custom_bridge, encoding="utf-8")

    result = connect_module.connect(root, Harness.claude_code, strict=False)

    assert (root / "CLAUDE.md").read_text() == custom_bridge
    assert any("CLAUDE.md" in warning for warning in result.warned)


# --- codex ------------------------------------------------------------------


def test_codex_writes_hooks_json_with_no_bridge(tmp_path: Path) -> None:
    root = _project(tmp_path)

    result = connect_module.connect(root, Harness.codex, strict=False)

    assert result.written == (
        (".codex/hooks.json", *_skill_files(connect_module._SKILLS_ROOT_SHARED), "smairt.yaml")
    )
    payload = json.loads((root / ".codex" / "hooks.json").read_text())
    assert payload["hooks"]["Stop"][0]["hooks"][0]["command"] == "smairt hook report"


def test_codex_strict_hooks_adds_pre_tool_use(tmp_path: Path) -> None:
    root = _project(tmp_path)

    connect_module.connect(root, Harness.codex, strict=True)

    payload = json.loads((root / ".codex" / "hooks.json").read_text())
    assert payload["hooks"]["PreToolUse"][0]["hooks"][0]["command"] == "smairt hook gate"


def test_codex_second_run_is_a_no_op(tmp_path: Path) -> None:
    root = _project(tmp_path)
    connect_module.connect(root, Harness.codex, strict=False)

    result = connect_module.connect(root, Harness.codex, strict=False)

    assert result.written == ()
    assert result.skipped == (
        ".codex/hooks.json",
        *_skill_files(connect_module._SKILLS_ROOT_SHARED),
    )


def test_codex_researcher_edited_hook_file_is_warned_about_and_untouched(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / ".codex").mkdir()
    custom = '{"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo hi"}]}]}}'
    (root / ".codex" / "hooks.json").write_text(custom, encoding="utf-8")

    result = connect_module.connect(root, Harness.codex, strict=False)

    assert (root / ".codex" / "hooks.json").read_text() == custom
    assert any(".codex/hooks.json" in warning for warning in result.warned)


# --- cursor -------------------------------------------------------------------


def test_cursor_writes_hooks_json_and_rule(tmp_path: Path) -> None:
    root = _project(tmp_path)

    result = connect_module.connect(root, Harness.cursor, strict=False)

    assert result.written == (
        ".cursor/hooks.json",
        ".cursor/rules/smairt.mdc",
        *_skill_files(connect_module._SKILLS_ROOT_SHARED),
        "smairt.yaml",
    )
    payload = json.loads((root / ".cursor" / "hooks.json").read_text())
    assert payload["version"] == 1
    assert payload["hooks"]["stop"][0]["command"] == "smairt hook report"


def test_cursor_rule_is_always_applied_and_points_at_the_contract(tmp_path: Path) -> None:
    root = _project(tmp_path)

    connect_module.connect(root, Harness.cursor, strict=False)

    content = (root / ".cursor" / "rules" / "smairt.mdc").read_text()
    assert content.startswith("---\n")
    assert "alwaysApply: true" in content
    assert "AGENTS.md" in content


def test_cursor_strict_hooks_adds_pre_tool_use(tmp_path: Path) -> None:
    root = _project(tmp_path)

    connect_module.connect(root, Harness.cursor, strict=True)

    payload = json.loads((root / ".cursor" / "hooks.json").read_text())
    assert payload["hooks"]["preToolUse"][0]["command"] == "smairt hook gate"


# --- opencode -------------------------------------------------------------------


def test_opencode_writes_a_plugin_file(tmp_path: Path) -> None:
    root = _project(tmp_path)

    result = connect_module.connect(root, Harness.opencode, strict=False)

    assert result.written == (
        ".opencode/plugins/smairt-check.ts",
        *_skill_files(connect_module._SKILLS_ROOT_SHARED),
        "smairt.yaml",
    )
    content = (root / ".opencode" / "plugins" / "smairt-check.ts").read_text()
    assert "smairt hook report" in content
    assert '"tool.execute.before":' not in content  # the actual hook, not the doc comment


def test_opencode_strict_hooks_adds_blocking_tool_hook(tmp_path: Path) -> None:
    root = _project(tmp_path)

    connect_module.connect(root, Harness.opencode, strict=True)

    content = (root / ".opencode" / "plugins" / "smairt-check.ts").read_text()
    assert "tool.execute.before" in content
    assert "smairt hook gate" in content


def test_opencode_second_run_is_a_no_op(tmp_path: Path) -> None:
    root = _project(tmp_path)
    connect_module.connect(root, Harness.opencode, strict=False)

    result = connect_module.connect(root, Harness.opencode, strict=False)

    assert result.written == ()
    assert result.skipped == (
        ".opencode/plugins/smairt-check.ts",
        *_skill_files(connect_module._SKILLS_ROOT_SHARED),
    )


# --- pi -------------------------------------------------------------------------


def test_pi_writes_an_extension_file(tmp_path: Path) -> None:
    root = _project(tmp_path)

    result = connect_module.connect(root, Harness.pi, strict=False)

    assert result.written == (
        ".pi/extensions/smairt-check.ts",
        *_skill_files(connect_module._SKILLS_ROOT_SHARED),
        "smairt.yaml",
    )
    content = (root / ".pi" / "extensions" / "smairt-check.ts").read_text()
    assert "export default function (pi: ExtensionAPI)" in content
    assert 'pi.on("agent_end"' in content
    assert "smairt hook report" in content
    assert 'pi.on("tool_call"' not in content


def test_pi_strict_hooks_adds_blocking_tool_call_handler(tmp_path: Path) -> None:
    root = _project(tmp_path)

    connect_module.connect(root, Harness.pi, strict=True)

    content = (root / ".pi" / "extensions" / "smairt-check.ts").read_text()
    assert 'pi.on("tool_call"' in content
    assert "smairt hook gate" in content
    assert "block: true" in content


def test_pi_second_run_is_a_no_op(tmp_path: Path) -> None:
    root = _project(tmp_path)
    connect_module.connect(root, Harness.pi, strict=False)

    result = connect_module.connect(root, Harness.pi, strict=False)

    assert result.written == ()
    assert result.skipped == (
        ".pi/extensions/smairt-check.ts",
        *_skill_files(connect_module._SKILLS_ROOT_SHARED),
    )


def test_pi_researcher_edited_extension_is_warned_about_and_untouched(tmp_path: Path) -> None:
    root = _project(tmp_path)
    extension_dir = root / ".pi" / "extensions"
    extension_dir.mkdir(parents=True)
    custom = "export default function () {}\n"
    (extension_dir / "smairt-check.ts").write_text(custom, encoding="utf-8")

    result = connect_module.connect(root, Harness.pi, strict=False)

    assert (extension_dir / "smairt-check.ts").read_text() == custom
    assert any(".pi/extensions/smairt-check.ts" in warning for warning in result.warned)


# --- gemini-cli -----------------------------------------------------------------


def test_gemini_writes_settings_with_context_filename_and_session_end_hook(tmp_path: Path) -> None:
    root = _project(tmp_path)

    result = connect_module.connect(root, Harness.gemini_cli, strict=False)

    assert result.written == (
        *_skill_files(connect_module._SKILLS_ROOT_SHARED),
        ".gemini/settings.json",
        "smairt.yaml",
    )
    payload = json.loads((root / ".gemini" / "settings.json").read_text())
    assert "AGENTS.md" in payload["context"]["fileName"]
    assert payload["hooks"]["SessionEnd"][0]["command"] == "smairt hook report"
    assert "BeforeTool" not in payload["hooks"]


def test_gemini_strict_hooks_adds_before_tool_blocking_hook(tmp_path: Path) -> None:
    root = _project(tmp_path)

    connect_module.connect(root, Harness.gemini_cli, strict=True)

    payload = json.loads((root / ".gemini" / "settings.json").read_text())
    assert payload["hooks"]["BeforeTool"][0]["command"] == "smairt hook gate"


def test_gemini_second_run_is_a_no_op(tmp_path: Path) -> None:
    root = _project(tmp_path)
    connect_module.connect(root, Harness.gemini_cli, strict=False)

    result = connect_module.connect(root, Harness.gemini_cli, strict=False)

    assert result.written == ()
    assert result.skipped == (
        *_skill_files(connect_module._SKILLS_ROOT_SHARED),
        ".gemini/settings.json",
    )


def test_gemini_merges_into_an_existing_settings_file_without_clobbering_it(tmp_path: Path) -> None:
    root = _project(tmp_path)
    gemini_dir = root / ".gemini"
    gemini_dir.mkdir()
    existing = {"telemetry": {"enabled": False}, "tools": {"core": ["ReadFileTool"]}}
    (gemini_dir / "settings.json").write_text(json.dumps(existing), encoding="utf-8")

    result = connect_module.connect(root, Harness.gemini_cli, strict=False)

    payload = json.loads((gemini_dir / "settings.json").read_text())
    # Researcher's pre-existing settings survive untouched.
    assert payload["telemetry"] == {"enabled": False}
    assert payload["tools"] == {"core": ["ReadFileTool"]}
    # smairt's keys were merged in.
    assert "AGENTS.md" in payload["context"]["fileName"]
    assert payload["hooks"]["SessionEnd"][0]["command"] == "smairt hook report"
    assert ".gemini/settings.json" in result.written


def test_gemini_never_clobbers_a_researcher_customized_context_filename(tmp_path: Path) -> None:
    root = _project(tmp_path)
    gemini_dir = root / ".gemini"
    gemini_dir.mkdir()
    existing = {"context": {"fileName": "GEMINI.md"}}
    (gemini_dir / "settings.json").write_text(json.dumps(existing), encoding="utf-8")

    connect_module.connect(root, Harness.gemini_cli, strict=False)

    payload = json.loads((gemini_dir / "settings.json").read_text())
    assert payload["context"]["fileName"] == "GEMINI.md"  # left exactly as the researcher set it
    assert payload["hooks"]["SessionEnd"][0]["command"] == "smairt hook report"  # still merged in


def test_gemini_invalid_json_is_warned_about_and_untouched(tmp_path: Path) -> None:
    root = _project(tmp_path)
    gemini_dir = root / ".gemini"
    gemini_dir.mkdir()
    (gemini_dir / "settings.json").write_text("{not valid json", encoding="utf-8")

    result = connect_module.connect(root, Harness.gemini_cli, strict=False)

    assert (gemini_dir / "settings.json").read_text() == "{not valid json"
    assert any(".gemini/settings.json" in warning for warning in result.warned)


# --- skills -----------------------------------------------------------------------


def _frontmatter_fields(skill_md_text: str) -> dict[str, object]:
    """Parse a skill file's ``---``-delimited frontmatter as YAML, for assertions."""
    _, _, rest = skill_md_text.partition("---\n")
    frontmatter_text, _, _ = rest.partition("\n---\n")
    parsed = yaml.safe_load(frontmatter_text)
    assert isinstance(parsed, dict)
    return parsed


def test_claude_code_installs_every_shipped_skill_at_dot_claude_skills(tmp_path: Path) -> None:
    root = _project(tmp_path)

    result = connect_module.connect(root, Harness.claude_code, strict=False)

    for name in list_skills():
        relative = f".claude/skills/{name}/SKILL.md"
        assert relative in result.written
        text = (root / relative).read_text()
        assert text.startswith("---\n")  # frontmatter must open on line 1
        fields = _frontmatter_fields(text)
        assert fields["name"] == name


@pytest.mark.parametrize(
    "harness", [Harness.codex, Harness.cursor, Harness.opencode, Harness.gemini_cli, Harness.pi]
)
def test_the_five_shared_harnesses_install_every_shipped_skill_at_dot_agents_skills(
    tmp_path: Path, harness: Harness
) -> None:
    root = _project(tmp_path / harness.value)

    result = connect_module.connect(root, harness, strict=False)

    for name in list_skills():
        relative = f".agents/skills/{name}/SKILL.md"
        assert relative in result.written
        text = (root / relative).read_text()
        assert text.startswith("---\n")
        assert _frontmatter_fields(text)["name"] == name


def test_installed_skill_carries_the_provenance_notice_after_the_frontmatter(
    tmp_path: Path,
) -> None:
    root = _project(tmp_path)

    connect_module.connect(root, Harness.claude_code, strict=False)

    text = (root / ".claude" / "skills" / "smairt-orient" / "SKILL.md").read_text()
    frontmatter, _, rest = text.partition("---\n")
    _, _, body = rest.partition("---\n")
    assert "Copied by `smairt connect claude-code`" in body
    # The notice sits in the body, after the frontmatter closes -- never before
    # the opening delimiter, which would break Cursor's and OpenCode's parsers.
    assert body.index("Copied by") < body.index("# SMAIRT Orient")


def test_shared_skill_provenance_notice_does_not_name_a_specific_harness(tmp_path: Path) -> None:
    """Naming a harness in the shared copy would break the free cross-harness idempotency."""
    root = _project(tmp_path)

    connect_module.connect(root, Harness.codex, strict=False)

    text = (root / ".agents" / "skills" / "smairt-orient" / "SKILL.md").read_text()
    assert "Copied by `smairt connect <harness>`" in text
    for other in ("codex", "cursor", "opencode", "gemini-cli", "pi"):
        assert f"connect {other}" not in text


def test_only_adversarial_review_gets_disable_model_invocation(tmp_path: Path) -> None:
    root = _project(tmp_path)

    connect_module.connect(root, Harness.claude_code, strict=False)

    restricted = (
        root / ".claude" / "skills" / "smairt-adversarial-review" / "SKILL.md"
    ).read_text()
    assert _frontmatter_fields(restricted)["disable-model-invocation"] is True

    for name in list_skills():
        if name == "smairt-adversarial-review":
            continue
        text = (root / ".claude" / "skills" / name / "SKILL.md").read_text()
        assert "disable-model-invocation" not in _frontmatter_fields(text)


def test_no_harness_gets_a_codex_openai_yaml_policy_sidecar(tmp_path: Path) -> None:
    """Codex's ``agents/openai.yaml`` policy file is deliberately never written.

    It is the documented Codex counterpart to ``disable-model-invocation``, but
    measured against ``codex-cli 0.146.0`` it removes the skill from the injected
    list entirely rather than only suppressing automatic selection. Since
    ``smairt-adversarial-review`` has no use except explicit researcher
    invocation, writing it would delete the mechanism rather than enforce it --
    see the "Judgment calls" note in ``connect.py``'s module docstring.
    """
    root = _project(tmp_path)

    connect_module.connect(root, Harness.codex, strict=False)
    connect_module.connect(root, Harness.claude_code, strict=False)

    for skills_root in (".agents/skills", ".claude/skills"):
        for name in list_skills():
            assert not (root / skills_root / name / "agents").exists()


def test_connecting_a_second_shared_harness_finds_skills_already_installed(tmp_path: Path) -> None:
    """The shared ``.agents/skills/`` target is free: the second harness connected
    to a project sees byte-identical skill files and reports them ``skipped``,
    never rewriting or warning about them.
    """
    root = _project(tmp_path)
    connect_module.connect(root, Harness.codex, strict=False)

    result = connect_module.connect(root, Harness.cursor, strict=False)

    for relative in _skill_files(connect_module._SKILLS_ROOT_SHARED):
        assert relative in result.skipped
        assert relative not in result.written
    assert result.warned == ()


def test_claude_code_never_overwrites_a_researcher_edited_skill(tmp_path: Path) -> None:
    root = _project(tmp_path)
    skill_dir = root / ".claude" / "skills" / "smairt-orient"
    skill_dir.mkdir(parents=True)
    custom = "---\nname: smairt-orient\ndescription: my own version\n---\n\nMy own text.\n"
    (skill_dir / "SKILL.md").write_text(custom, encoding="utf-8")

    result = connect_module.connect(root, Harness.claude_code, strict=False)

    assert (skill_dir / "SKILL.md").read_text() == custom
    assert any(".claude/skills/smairt-orient/SKILL.md" in warning for warning in result.warned)


def test_shared_researcher_edited_skill_is_warned_about_and_left_untouched(tmp_path: Path) -> None:
    root = _project(tmp_path)
    skill_dir = root / ".agents" / "skills" / "smairt-orient"
    skill_dir.mkdir(parents=True)
    custom = "---\nname: smairt-orient\ndescription: my own version\n---\n\nMy own text.\n"
    (skill_dir / "SKILL.md").write_text(custom, encoding="utf-8")

    result = connect_module.connect(root, Harness.codex, strict=False)

    assert (skill_dir / "SKILL.md").read_text() == custom
    assert any(".agents/skills/smairt-orient/SKILL.md" in warning for warning in result.warned)


# --- project scoping -----------------------------------------------------------


def test_every_harness_only_ever_writes_inside_the_project(tmp_path: Path) -> None:
    """Every path ``connect()`` reports for every harness must resolve inside the project.

    Regression test for the scoping guarantee stated in ``connect.py``'s module
    docstring and enforced by ``_write_or_warn``'s guard: nothing this module
    writes should ever be able to land outside the project root it was given
    (``$HOME``, a harness's global config, ...). Runs every registered harness
    (skipping ``Harness.none``, which has no wiring) against a fresh project
    each time so one harness's files can't make another's assertions moot.
    """
    for harness in connect_module._HARNESS_HANDLERS:
        root = _project(tmp_path / harness.value)
        result = connect_module.connect(root, harness, strict=True)
        for relative in result.written + result.skipped:
            assert not Path(relative).is_absolute(), (harness, relative)
            resolved = (root / relative).resolve()
            assert resolved.is_relative_to(root.resolve()), (harness, relative, resolved)


def test_generated_claude_settings_state_the_project_scoping_guarantee(tmp_path: Path) -> None:
    root = _project(tmp_path)

    connect_module.connect(root, Harness.claude_code, strict=False)

    payload = json.loads((root / ".claude" / "settings.json").read_text())
    assert "Project-scoped:" in payload["_comment"]


# --- smairt.yaml harnesses: list -------------------------------------------------


def test_connect_records_the_harness_in_smairt_yaml(tmp_path: Path) -> None:
    root = _project(tmp_path, harness=Harness.none)
    assert yaml.safe_load((root / "smairt.yaml").read_text())["harnesses"] == []

    connect_module.connect(root, Harness.codex, strict=False)

    assert yaml.safe_load((root / "smairt.yaml").read_text())["harnesses"] == ["codex"]


def test_connect_does_not_duplicate_an_already_recorded_harness(tmp_path: Path) -> None:
    root = _project(tmp_path, harness=Harness.claude_code)
    assert yaml.safe_load((root / "smairt.yaml").read_text())["harnesses"] == ["claude-code"]

    connect_module.connect(root, Harness.claude_code, strict=False)

    assert yaml.safe_load((root / "smairt.yaml").read_text())["harnesses"] == ["claude-code"]


def test_connect_appends_a_second_harness_alongside_the_first(tmp_path: Path) -> None:
    root = _project(tmp_path, harness=Harness.claude_code)

    connect_module.connect(root, Harness.codex, strict=False)

    assert yaml.safe_load((root / "smairt.yaml").read_text())["harnesses"] == [
        "claude-code",
        "codex",
    ]


def test_connect_none_harness_is_rejected() -> None:
    with pytest.raises(ValueError):
        connect_module.connect(Path("/does/not/matter"), Harness.none, strict=False)


# --- CI template ------------------------------------------------------------------


def test_connect_ci_writes_the_github_actions_workflow(tmp_path: Path) -> None:
    root = _project(tmp_path)

    result = connect_module.connect_ci(root)

    assert result.written == (".github/workflows/smairt-check.yml",)
    content = (root / ".github" / "workflows" / "smairt-check.yml").read_text()
    assert "smairt check" in content
    assert "on:" in content


def test_connect_ci_second_run_is_a_no_op(tmp_path: Path) -> None:
    root = _project(tmp_path)
    connect_module.connect_ci(root)

    result = connect_module.connect_ci(root)

    assert result.written == ()
    assert result.skipped == (".github/workflows/smairt-check.yml",)


def test_connect_ci_never_overwrites_a_researcher_edited_workflow(tmp_path: Path) -> None:
    root = _project(tmp_path)
    workflow_dir = root / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)
    custom = "name: my own workflow\non: [push]\n"
    (workflow_dir / "smairt-check.yml").write_text(custom, encoding="utf-8")

    result = connect_module.connect_ci(root)

    assert (workflow_dir / "smairt-check.yml").read_text() == custom
    assert any("smairt-check.yml" in warning for warning in result.warned)


# --- CLI surface --------------------------------------------------------------


def test_cli_connect_claude_code_writes_the_stop_hook(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _project(tmp_path)
    monkeypatch.chdir(root)

    result = runner.invoke(app, ["connect", "claude-code"])

    assert result.exit_code == 0, result.output
    assert (root / ".claude" / "settings.json").is_file()
    assert "Wrote .claude/settings.json" in result.output


def test_cli_connect_second_run_reports_no_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _project(tmp_path)
    monkeypatch.chdir(root)
    runner.invoke(app, ["connect", "claude-code"])

    result = runner.invoke(app, ["connect", "claude-code"])

    assert result.exit_code == 0, result.output
    assert "Wrote" not in result.output
    assert "Unchanged" in result.output


def test_cli_connect_honors_strict_hooks_from_smairt_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _project(tmp_path)
    config_path = root / "smairt.yaml"
    config = yaml.safe_load(config_path.read_text())
    config["settings"]["strict_hooks"] = True
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    monkeypatch.chdir(root)

    runner.invoke(app, ["connect", "claude-code"])

    payload = json.loads((root / ".claude" / "settings.json").read_text())
    assert "PreToolUse" in payload["hooks"]


def test_cli_connect_gemini_writes_settings_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _project(tmp_path)
    monkeypatch.chdir(root)

    result = runner.invoke(app, ["connect", "gemini-cli"])

    assert result.exit_code == 0, result.output
    assert (root / ".gemini" / "settings.json").is_file()


def test_cli_connect_ci_writes_the_workflow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _project(tmp_path)
    monkeypatch.chdir(root)

    result = runner.invoke(app, ["connect", "--ci"])

    assert result.exit_code == 0, result.output
    assert (root / ".github" / "workflows" / "smairt-check.yml").is_file()


def test_cli_connect_ci_subcommand_spelling_also_works(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _project(tmp_path)
    monkeypatch.chdir(root)

    result = runner.invoke(app, ["connect", "ci"])

    assert result.exit_code == 0, result.output
    assert (root / ".github" / "workflows" / "smairt-check.yml").is_file()


def test_cli_connect_rejects_an_unknown_harness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _project(tmp_path)
    monkeypatch.chdir(root)

    result = runner.invoke(app, ["connect", "not-a-real-harness"])

    assert result.exit_code != 0
    assert "unknown harness" in result.output


def test_cli_connect_refuses_outside_a_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["connect", "claude-code"])

    assert result.exit_code != 0
    assert "not a SMAIRT project" in result.output


def test_cli_new_with_harness_claude_code_produces_the_wiring_end_to_end(
    tmp_path: Path,
) -> None:
    result = runner.invoke(
        app,
        [
            "new",
            "--name",
            "End To End",
            "--researcher",
            "Ada Lovelace",
            "--description",
            "Exercises smairt new -> connect end to end.",
            "--path",
            str(tmp_path),
            "--harness",
            "claude-code",
            "--no-hpc",
            "--no-paper",
        ],
        input="",
    )

    assert result.exit_code == 0, result.output
    root = tmp_path / "end_to_end"
    assert (root / ".claude" / "settings.json").is_file()
    payload = json.loads((root / ".claude" / "settings.json").read_text())
    assert payload["hooks"]["Stop"][0]["hooks"][0]["command"] == "smairt hook report"
    assert yaml.safe_load((root / "smairt.yaml").read_text())["harnesses"] == ["claude-code"]
