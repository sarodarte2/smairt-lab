"""Responsive terminal and five-harness adapter contracts."""

from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import Mock

from rich.console import Console

from smairt.harness_presentation import HARNESS_PRESENTATIONS
from smairt.harnesses import configure_mcp, harness_status, select_harness
from smairt.hook_policy import hook_response, parse_hook_payload, policy_denial
from smairt.models import DataClassification, HarnessName
from smairt.project import context
from smairt.scaffold import create_project
from smairt.workflows import WORKFLOW_SLUGS


def project(tmp_path: Path) -> Path:
    root = tmp_path / "five-harnesses"
    create_project(
        root,
        name="Five Harnesses",
        author="Researcher",
        classification=DataClassification.UNPUBLISHED,
        initialize_git=False,
        confirm_contributor=True,
    )
    return root


def test_every_harness_has_a_repository_guide() -> None:
    repository = Path(__file__).parents[1]
    assert set(HARNESS_PRESENTATIONS) == set(HarnessName)
    for details in HARNESS_PRESENTATIONS.values():
        assert (repository / details.guide).is_file()


def test_opencode_and_cursor_adapters_are_hardened_and_mcp_capable(tmp_path: Path) -> None:
    root = project(tmp_path)
    select_harness(root, "opencode")
    opencode = json.loads((root / "opencode.json").read_text())
    assert opencode["permission"]["external_directory"] == "deny"
    assert opencode["permission"]["bash"]["git push --force*"] == "deny"
    assert not (root / ".opencode/plugins").exists()
    configure_mcp(root, HarnessName.OPENCODE, True)
    assert json.loads((root / "opencode.json").read_text())["mcp"]["smairt"]["enabled"]

    select_harness(root, "cursor")
    hooks = json.loads((root / ".cursor/hooks.json").read_text())
    assert hooks["hooks"]["preToolUse"][0]["failClosed"] is True
    assert (root / ".cursor/hooks/smairt-hook").stat().st_mode & 0o111
    configure_mcp(root, HarnessName.CURSOR, True)
    assert "smairt" in json.loads((root / ".cursor/mcp.json").read_text())["mcpServers"]
    assert harness_status(root)["capabilities"]["protected_operation_hook"] == "blocking"


def test_all_harnesses_have_truthful_capability_records(tmp_path: Path) -> None:
    root = project(tmp_path)
    for harness in HarnessName:
        result = select_harness(root, harness.value)
        assert result["harness"] == harness.value
        assert "protected_operation_hook" in result["capabilities"]
        assert configure_mcp(root, harness, True)["enabled"] is True
    assert harness_status(root, "zoo")["capabilities"]["protected_operation_hook"] == "unsupported"


def test_six_workflows_and_native_reviewers_are_generated(tmp_path: Path) -> None:
    root = project(tmp_path)
    for slug in WORKFLOW_SLUGS:
        assert (root / f".agents/skills/{slug}/SKILL.md").exists()
    assert not (root / ".agents/skills/smairt-research").exists()
    assert (root / ".codex/agents/smairt-reviewer.toml").exists()

    select_harness(root, "cline")
    for slug in WORKFLOW_SLUGS:
        assert (root / f".cline/workflows/{slug}.md").exists()

    select_harness(root, "opencode")
    assert (root / ".opencode/agents/smairt-reviewer.md").exists()
    select_harness(root, "cursor")
    assert (root / ".cursor/agents/smairt-reviewer.md").exists()
    cursor_permissions = json.loads((root / ".cursor/cli.json").read_text())["permissions"]
    assert cursor_permissions["deny"]
    assert "Shell(git)" not in cursor_permissions["allow"]


def test_review_context_is_bounded_and_rejects_protected_targets(tmp_path: Path) -> None:
    root = project(tmp_path)
    target = root / "plans/review-me.md"
    target.write_text("# Review me\n")
    packet = context(root, "review", target="plans/review-me.md")
    assert packet["review_target"] == "plans/review-me.md"
    assert packet["mutation_allowed"] is False
    assert "plans/review-me.md" in packet["read"]

    protected = root / "data/raw/secret.txt"
    protected.parent.mkdir(parents=True, exist_ok=True)
    protected.write_text("protected\n")
    try:
        context(root, "review", target="data/raw/secret.txt")
    except ValueError as exc:
        assert "protected" in str(exc)
    else:
        raise AssertionError("protected review target was accepted")


def test_hook_policy_bounds_and_denies_protected_or_human_gate_operations(tmp_path: Path) -> None:
    root = project(tmp_path)
    payload = parse_hook_payload(b'{"tool_name":"Bash","tool_input":{"command":"git status"}}')
    assert policy_denial(payload) is None
    protected = {"tool_name": "apply_patch", "tool_input": {"command": "data/raw/x.fast5"}}
    assert "Protected" in str(policy_denial(protected))
    human = {
        "tool_name": "Bash",
        "tool_input": {"command": "smairt decision record --decision ACCEPT"},
    }
    codex = hook_response(root, "codex", "PreToolUse", human)
    assert codex["hookSpecificOutput"]["permissionDecision"] == "deny"
    cline = hook_response(root, "cline", "PreToolUse", human)
    assert cline["cancel"] is True
    claim = {
        "tool_name": "Bash",
        "tool_input": {"command": "smairt paper claim approve claim-1 --yes"},
    }
    assert "human scientific gate" in str(policy_denial(claim)).lower()
    results_edit = {
        "tool_name": "Write",
        "tool_input": {"path": "results/EXPERIMENT_001/ITERATION_001/RUN_1/run.json"},
    }
    assert "Immutable" in str(policy_denial(results_edit))
    selection_edit = {
        "tool_name": "Edit",
        "tool_input": {"path": "analysis/EXPERIMENT_001/selection.yaml"},
    }
    assert "Immutable" in str(policy_denial(selection_edit))


def test_responsive_header_uses_compact_and_wide_branding(monkeypatch) -> None:
    from smairt import tui

    monkeypatch.setenv("SMAIRT_REDUCED_MOTION", "1")
    narrow_buffer = io.StringIO()
    narrow = Console(file=narrow_buffer, width=50, height=14, force_terminal=False)
    monkeypatch.setattr(tui, "console", narrow)
    tui._header("Project", "Health and next step")
    assert "◆ SMAIRT · Project" in narrow_buffer.getvalue()

    wide_buffer = io.StringIO()
    wide = Console(file=wide_buffer, width=130, height=40, force_terminal=True)
    wide.clear = Mock()  # type: ignore[method-assign]
    monkeypatch.setattr(tui, "console", wide)
    tui._header("Project", "Health and next step")
    tui._header("References", "Metadata and PDFs")
    assert wide.clear.call_count == 2
    assert "Scientific Method" in wide_buffer.getvalue()
