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


# --- claude-code ----------------------------------------------------------------


def test_claude_code_writes_bridge_and_stop_hook(tmp_path: Path) -> None:
    root = _project(tmp_path)

    result = connect_module.connect(root, Harness.claude_code, strict=False)

    assert "CLAUDE.md" in result.skipped  # create_project already wrote the bridge
    assert ".claude/settings.json" in result.written
    payload = json.loads((root / ".claude" / "settings.json").read_text())
    assert "_comment" in payload
    assert payload["hooks"]["Stop"][0]["hooks"][0]["command"] == "smairt check"
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
    assert set(result.skipped) == {"CLAUDE.md", ".claude/settings.json"}
    assert result.warned == ()


def test_claude_code_strict_hooks_adds_pre_tool_use_blocking_config(tmp_path: Path) -> None:
    root = _project(tmp_path)

    connect_module.connect(root, Harness.claude_code, strict=True)

    payload = json.loads((root / ".claude" / "settings.json").read_text())
    pre_tool_use = payload["hooks"]["PreToolUse"][0]
    assert pre_tool_use["hooks"][0]["command"] == "smairt check --json"
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

    assert result.written == (".codex/hooks.json", "smairt.yaml")
    payload = json.loads((root / ".codex" / "hooks.json").read_text())
    assert payload["hooks"]["Stop"][0]["hooks"][0]["command"] == "smairt check"


def test_codex_strict_hooks_adds_pre_tool_use(tmp_path: Path) -> None:
    root = _project(tmp_path)

    connect_module.connect(root, Harness.codex, strict=True)

    payload = json.loads((root / ".codex" / "hooks.json").read_text())
    assert payload["hooks"]["PreToolUse"][0]["hooks"][0]["command"] == "smairt check --json"


def test_codex_second_run_is_a_no_op(tmp_path: Path) -> None:
    root = _project(tmp_path)
    connect_module.connect(root, Harness.codex, strict=False)

    result = connect_module.connect(root, Harness.codex, strict=False)

    assert result.written == ()
    assert result.skipped == (".codex/hooks.json",)


def test_codex_researcher_edited_hook_file_is_warned_about_and_untouched(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / ".codex").mkdir()
    custom = '{"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo hi"}]}]}}'
    (root / ".codex" / "hooks.json").write_text(custom, encoding="utf-8")

    result = connect_module.connect(root, Harness.codex, strict=False)

    assert (root / ".codex" / "hooks.json").read_text() == custom
    assert any(".codex/hooks.json" in warning for warning in result.warned)


# --- cursor -------------------------------------------------------------------


def test_cursor_writes_hooks_json(tmp_path: Path) -> None:
    root = _project(tmp_path)

    result = connect_module.connect(root, Harness.cursor, strict=False)

    assert result.written == (".cursor/hooks.json", "smairt.yaml")
    payload = json.loads((root / ".cursor" / "hooks.json").read_text())
    assert payload["hooks"]["stop"][0]["command"] == "smairt check"


def test_cursor_strict_hooks_adds_pre_tool_use(tmp_path: Path) -> None:
    root = _project(tmp_path)

    connect_module.connect(root, Harness.cursor, strict=True)

    payload = json.loads((root / ".cursor" / "hooks.json").read_text())
    assert payload["hooks"]["preToolUse"][0]["command"] == "smairt check --json"


# --- opencode -------------------------------------------------------------------


def test_opencode_writes_a_plugin_file(tmp_path: Path) -> None:
    root = _project(tmp_path)

    result = connect_module.connect(root, Harness.opencode, strict=False)

    assert result.written == (".opencode/plugins/smairt-check.ts", "smairt.yaml")
    content = (root / ".opencode" / "plugins" / "smairt-check.ts").read_text()
    assert "smairt check" in content
    assert '"tool.execute.before":' not in content  # the actual hook, not the doc comment


def test_opencode_strict_hooks_adds_blocking_tool_hook(tmp_path: Path) -> None:
    root = _project(tmp_path)

    connect_module.connect(root, Harness.opencode, strict=True)

    content = (root / ".opencode" / "plugins" / "smairt-check.ts").read_text()
    assert "tool.execute.before" in content
    assert "smairt check --json" in content


def test_opencode_second_run_is_a_no_op(tmp_path: Path) -> None:
    root = _project(tmp_path)
    connect_module.connect(root, Harness.opencode, strict=False)

    result = connect_module.connect(root, Harness.opencode, strict=False)

    assert result.written == ()
    assert result.skipped == (".opencode/plugins/smairt-check.ts",)


# --- gemini-cli -----------------------------------------------------------------


def test_gemini_writes_settings_with_context_filename_and_session_end_hook(tmp_path: Path) -> None:
    root = _project(tmp_path)

    result = connect_module.connect(root, Harness.gemini_cli, strict=False)

    assert result.written == (".gemini/settings.json", "smairt.yaml")
    payload = json.loads((root / ".gemini" / "settings.json").read_text())
    assert "AGENTS.md" in payload["context"]["fileName"]
    assert payload["hooks"]["SessionEnd"][0]["command"] == "smairt check"
    assert "BeforeTool" not in payload["hooks"]


def test_gemini_strict_hooks_adds_before_tool_blocking_hook(tmp_path: Path) -> None:
    root = _project(tmp_path)

    connect_module.connect(root, Harness.gemini_cli, strict=True)

    payload = json.loads((root / ".gemini" / "settings.json").read_text())
    assert payload["hooks"]["BeforeTool"][0]["command"] == "smairt check --json"


def test_gemini_second_run_is_a_no_op(tmp_path: Path) -> None:
    root = _project(tmp_path)
    connect_module.connect(root, Harness.gemini_cli, strict=False)

    result = connect_module.connect(root, Harness.gemini_cli, strict=False)

    assert result.written == ()
    assert result.skipped == (".gemini/settings.json",)


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
    assert payload["hooks"]["SessionEnd"][0]["command"] == "smairt check"
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
    assert payload["hooks"]["SessionEnd"][0]["command"] == "smairt check"  # still merged in


def test_gemini_invalid_json_is_warned_about_and_untouched(tmp_path: Path) -> None:
    root = _project(tmp_path)
    gemini_dir = root / ".gemini"
    gemini_dir.mkdir()
    (gemini_dir / "settings.json").write_text("{not valid json", encoding="utf-8")

    result = connect_module.connect(root, Harness.gemini_cli, strict=False)

    assert (gemini_dir / "settings.json").read_text() == "{not valid json"
    assert any(".gemini/settings.json" in warning for warning in result.warned)


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
    assert payload["hooks"]["Stop"][0]["hooks"][0]["command"] == "smairt check"
    assert yaml.safe_load((root / "smairt.yaml").read_text())["harnesses"] == ["claude-code"]
