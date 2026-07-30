"""Bounded, offline policy translation for coding-harness lifecycle hooks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from smairt.guidance import next_guidance, render_suggested_prompt

MAX_HOOK_BYTES = 1024 * 1024
PROTECTED_TOKENS = (
    ".env",
    ".pem",
    ".key",
    ".smairt/local",
    "data/raw/",
    "references/pdfs/",
    ".fast5",
    ".pod5",
    "api_key",
    "access_token",
)
IMMUTABLE_EDIT_TOKENS = (
    "results/",
    "evidence/",
    "selection.yaml",
    ".smairt/transactions/",
)
HUMAN_GATE_COMMANDS = (
    "smairt hypothesis activate",
    "smairt experiment new",
    "smairt decision record",
    "smairt paper claim approve",
    "smairt paper claim reject",
    "smairt paper evidence review",
    "smairt paper section review",
    "smairt safety set",
    "smairt contributor use",
    "smairt amend",
    "smairt retract",
    "smairt supersede",
)
DESTRUCTIVE_COMMANDS = ("rm -rf /", "git reset --hard", "git clean -fd", "git push --force")


def parse_hook_payload(raw: bytes) -> dict[str, Any]:
    """Parse a bounded JSON object without accepting trailing or scalar input."""
    if len(raw) > MAX_HOOK_BYTES:
        raise ValueError("hook payload exceeds the 1 MiB safety bound")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("hook payload must be one UTF-8 JSON object") from exc
    if not isinstance(payload, dict):
        raise ValueError("hook payload root must be an object")
    return payload


def _flatten(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True).lower()


def _tool_name(payload: dict[str, Any]) -> str:
    nested = payload.get("preToolUse")
    nested_tool = nested.get("tool", "") if isinstance(nested, dict) else ""
    return str(payload.get("tool_name") or payload.get("toolName") or nested_tool).lower()


def policy_denial(payload: dict[str, Any]) -> str | None:
    """Return a user-facing denial reason for one protected operation."""
    flattened = _flatten(payload)
    if any(token in flattened for token in PROTECTED_TOKENS):
        return "Protected local data, PDFs, or credentials are outside agent access."
    tool = _tool_name(payload)
    mutating_tool = any(token in tool for token in ("write", "edit", "patch", "bash", "shell"))
    if mutating_tool and any(token in flattened for token in IMMUTABLE_EDIT_TOKENS):
        return "Immutable SMAIRT records must be changed through a reviewed SMAIRT workflow."
    if any(command in flattened for command in HUMAN_GATE_COMMANDS):
        return "This is a human scientific gate; run the command directly as the researcher."
    if any(command in flattened for command in DESTRUCTIVE_COMMANDS):
        return "Destructive repository or filesystem operation blocked by SMAIRT policy."
    return None


def context_message(root: Path) -> str:
    """Render bounded context suitable for session-start and compaction hooks."""
    return render_suggested_prompt(root, next_guidance(root))


def hook_response(root: Path, harness: str, event: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Translate SMAIRT policy into one harness's documented response shape."""
    pre_tool = event.lower() in {"pretooluse", "pre_tool_use"}
    denial = policy_denial(payload) if pre_tool else None
    if harness == "cline":
        return {
            "cancel": bool(denial),
            "contextModification": "" if pre_tool else context_message(root),
            "errorMessage": denial or "",
        }
    event_name = "PreToolUse" if pre_tool else event
    output: dict[str, Any] = {"hookEventName": event_name}
    if denial:
        output.update(permissionDecision="deny", permissionDecisionReason=denial)
    elif not pre_tool:
        output["additionalContext"] = context_message(root)
    return {"hookSpecificOutput": output}
