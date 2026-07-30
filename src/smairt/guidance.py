"""State-aware workflow guidance shared by the CLI and coding agents."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from smairt.integrity import verify_run
from smairt.models import ClaimRecord, EvidenceCard, RunRecord, RunStatus, SmairtConfig
from smairt.references import load_index
from smairt.research import (
    find_hypothesis,
    validate_background,
    validate_hypothesis,
    validate_proposal_set,
)


def _action(
    identifier: str,
    label: str,
    *,
    kind: str,
    recommended: bool = False,
    requires_human: bool = False,
    command: str | None = None,
    read: list[str] | None = None,
    prompt: str | None = None,
) -> dict[str, Any]:
    """Construct one stable Codex action with command, reading, or prompt metadata."""
    return {
        "id": identifier,
        "label": label,
        "kind": kind,
        "recommended": recommended,
        "requires_human": requires_human,
        "command": command,
        "read": read or [],
        "prompt": prompt,
    }


def _proposal_choices(path: Path) -> list[dict[str, Any]]:
    """Extract dynamic A/B/C hypothesis titles and add an explicit custom option."""
    content = path.read_text(encoding="utf-8")
    choices = []
    for label, title in re.findall(r"^## Option ([ABC]):\s*(.+)$", content, flags=re.MULTILINE):
        choices.append(
            _action(
                f"select_hypothesis_{label.lower()}",
                f"Option {label}: {title.strip()}",
                kind="human_choice",
                requires_human=True,
                read=[str(path)],
            )
        )
    choices.append(
        _action(
            "edit_or_custom_hypothesis",
            "Edit an option or provide a custom hypothesis",
            kind="human_choice",
            requires_human=True,
            read=[str(path)],
        )
    )
    return choices


def next_guidance(root: Path) -> dict[str, Any]:
    """Derive the next useful research action from durable project artifacts."""
    config = SmairtConfig.load(root / "smairt.yaml")
    references = load_index(root)
    background = root / "background/initial_background.md"
    proposals = sorted((root / "hypotheses/proposals").glob("PROPOSAL_SET_*.md"))
    experiments = sorted((root / "experiments").glob("EXPERIMENT_*"))
    if not config.active_contributor:
        return _guidance(
            "contributor_confirmation",
            "The project exists, but no contributor is confirmed as active.",
            [
                _action(
                    "confirm_contributor",
                    "Confirm and select the active contributor",
                    kind="human_choice",
                    recommended=True,
                    requires_human=True,
                    command="smairt contributor add --name '<name>'",
                )
            ],
        )
    if (
        config.data.classification.value in {"private", "controlled"}
        and not config.repository_attestation.acknowledged
    ):
        return _guidance(
            "repository_attestation",
            "Protected collaboration requires a repository visibility acknowledgment.",
            [
                _action(
                    "attest_repository",
                    "Confirm the repository visibility and collaboration practice",
                    kind="human_choice",
                    recommended=True,
                    requires_human=True,
                    command="smairt safety attest --visibility private",
                )
            ],
        )
    if experiments:
        hypothesis = (
            find_hypothesis(root, config.active.hypothesis) if config.active.hypothesis else None
        )
        has_run = bool(list((root / "results").glob("EXPERIMENT_*/*/RUN_*")))
        background_incomplete = (
            not background.exists()
            or background.read_text(encoding="utf-8").strip()
            == "# Initial Background\n\nStatus: DRAFT"
            or bool(validate_background(root))
        )
        # Prefer active experiment guidance once setup is in place or execution has begun.
        # Exploratory projects with only an empty experiment still receive setup catch-up.
        if has_run or not background_incomplete or config.active.hypothesis:
            return _active_experiment_guidance(root, config, experiments, hypothesis)

    if not references:
        return _guidance(
            "project_setup",
            "Project setup is complete.",
            [
                _action(
                    "add_references",
                    "Add and index relevant reference PDFs",
                    kind="prompt",
                    recommended=True,
                    prompt="Help me select and add a small set of relevant papers.",
                ),
                _action(
                    "review_question",
                    "Review the initial question and description",
                    kind="read",
                    read=["background/initial_question.md", "background/project_description.md"],
                ),
                _action(
                    "create_background_without_refs",
                    "Start a provisional background without references",
                    kind="command",
                    command="smairt background create",
                ),
            ],
        )
    if background.read_text(encoding="utf-8").strip() == "# Initial Background\n\nStatus: DRAFT":
        return _guidance(
            "references_indexed",
            f"{len(references)} reference(s) are indexed.",
            [
                _action(
                    "create_background",
                    "Create the initial-background workspace",
                    kind="command",
                    recommended=True,
                    command="smairt background create",
                ),
                _action(
                    "review_references",
                    "Review indexed reference metadata",
                    kind="read",
                    read=["references/index.yaml"],
                ),
            ],
        )
    if validate_background(root):
        return _guidance(
            "background_draft",
            "The initial-background workspace is ready.",
            [
                _action(
                    "complete_background",
                    "Synthesize the initial background from indexed references",
                    kind="prompt",
                    recommended=True,
                    read=["background/initial_background.md", "references/index.yaml"],
                    prompt=(
                        "Complete the initial background with reference IDs and page ranges; "
                        "separate evidence, inference, limitations, and gaps."
                    ),
                ),
                _action(
                    "review_background",
                    "Open and review the background draft",
                    kind="read",
                    read=["background/initial_background.md"],
                ),
            ],
        )
    if not proposals:
        return _guidance(
            "background_complete",
            "The initial background is complete.",
            [
                _action(
                    "create_proposals",
                    "Create a three-option hypothesis proposal set",
                    kind="command",
                    recommended=True,
                    command="smairt hypothesis proposals new",
                ),
                _action(
                    "exploratory_experiment",
                    "Start an exploratory experiment with an explicit purpose",
                    kind="command",
                    command=(
                        "smairt experiment new --title '<title>' --purpose '<exploratory purpose>'"
                    ),
                ),
                _action(
                    "review_background",
                    "Review the completed background first",
                    kind="read",
                    read=["background/initial_background.md"],
                ),
            ],
        )
    latest_proposal = proposals[-1]
    if validate_proposal_set(latest_proposal):
        return _guidance(
            "proposal_draft",
            f"{latest_proposal.name} is ready for development.",
            [
                _action(
                    "complete_proposals",
                    "Develop exactly three distinct hypothesis options",
                    kind="prompt",
                    recommended=True,
                    read=[str(latest_proposal), "background/initial_background.md"],
                    prompt=(
                        "Complete options A, B, and C with distinct reasoning, predictions, "
                        "alternatives, data, tests, feasibility, and confounders."
                    ),
                ),
                _action(
                    "review_proposal_template",
                    "Open the proposal set",
                    kind="read",
                    read=[str(latest_proposal)],
                ),
            ],
        )
    if not config.active.hypothesis:
        return _guidance(
            "proposal_complete",
            "Three hypothesis options are ready for review.",
            _proposal_choices(latest_proposal),
        )
    hypothesis = find_hypothesis(root, config.active.hypothesis)
    if validate_hypothesis(hypothesis):
        return _guidance(
            "hypothesis_selected",
            f"{config.active.hypothesis} was selected by the researcher.",
            [
                _action(
                    "complete_hypothesis",
                    "Complete the selected hypothesis before execution",
                    kind="prompt",
                    recommended=True,
                    read=[str(hypothesis)],
                    prompt=(
                        "Complete every required hypothesis section using the selected proposal "
                        "and preserve the human rationale."
                    ),
                ),
                _action(
                    "review_hypothesis",
                    "Read the selected hypothesis",
                    kind="read",
                    read=[str(hypothesis)],
                ),
            ],
        )
    if not experiments:
        return _guidance(
            "hypothesis_ready",
            f"{config.active.hypothesis} is complete and test-ready.",
            [
                _action(
                    "choose_experiment_route",
                    "Compare three experimental routes, then create one",
                    kind="human_choice",
                    recommended=True,
                    requires_human=True,
                    read=[str(hypothesis)],
                    prompt=(
                        "Offer three distinct experimental routes with rationale, tradeoffs, "
                        "required data, controls, and expected evidence."
                    ),
                    command=(
                        f"smairt experiment new --title '<title>' "
                        f"--hypothesis {config.active.hypothesis}"
                    ),
                ),
                _action(
                    "create_experiment",
                    "Create the chosen linked experiment",
                    kind="command",
                    command=(
                        f"smairt experiment new --title '<title>' "
                        f"--hypothesis {config.active.hypothesis}"
                    ),
                ),
                _action(
                    "review_hypothesis",
                    "Read the hypothesis before choosing",
                    kind="read",
                    read=[str(hypothesis)],
                ),
            ],
        )
    return _active_experiment_guidance(root, config, experiments, hypothesis)


def _active_experiment_guidance(
    root: Path,
    config: SmairtConfig,
    experiments: list[Path],
    hypothesis: Path | None,
) -> dict[str, Any]:
    """Prioritize active experiment, run, and decision artifacts over setup suggestions."""
    if hypothesis and validate_hypothesis(hypothesis):
        return _guidance(
            "hypothesis_selected",
            f"{config.active.hypothesis} is linked to an experiment but is incomplete.",
            [
                _action(
                    "complete_hypothesis",
                    "Complete the linked hypothesis before execution",
                    kind="prompt",
                    recommended=True,
                    read=[str(hypothesis)],
                    prompt=(
                        "Complete every required hypothesis section before running the experiment."
                    ),
                ),
                _action(
                    "review_hypothesis",
                    "Read the linked hypothesis",
                    kind="read",
                    read=[str(hypothesis)],
                ),
            ],
        )
    active_experiment = _experiment(root, config.active.experiment) or experiments[-1]
    metadata = yaml.safe_load((active_experiment / "experiment.yaml").read_text()) or {}
    iteration_id = config.active.iteration or "ITERATION_001"
    iteration = active_experiment / "iterations" / iteration_id
    run_directories = (
        sorted((root / "results" / str(metadata["id"]) / iteration_id).glob("RUN_*"))
        if (root / "results" / str(metadata["id"]) / iteration_id).exists()
        else []
    )
    if not run_directories:
        return _guidance(
            "experiment_ready",
            f"{metadata['id']} / {iteration_id} is ready for implementation and review.",
            [
                _action(
                    "implement_experiment",
                    "Implement and review the experiment code",
                    kind="prompt",
                    recommended=True,
                    read=[
                        str(iteration.relative_to(root)),
                        *([str(hypothesis)] if hypothesis else []),
                    ],
                    prompt=(
                        "Implement the registered experiment entrypoint using SMAIRT code "
                        "conventions, then run code validation."
                    ),
                ),
                _action(
                    "review_code",
                    "Open the generated experiment skeleton",
                    kind="read",
                    read=[str(iteration.relative_to(root))],
                ),
                _action(
                    "validate_code",
                    "Validate code readability and traceability",
                    kind="command",
                    command="smairt code validate",
                ),
            ],
        )
    runs: list[Path] = []
    for run_dir in run_directories:
        try:
            record = RunRecord.model_validate_json(
                (run_dir / "run.json").read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            continue
        if (
            record.run_id == run_dir.name
            and record.experiment_id == str(metadata["id"])
            and record.iteration_id == iteration_id
            and record.status is RunStatus.COMPLETED
            and record.exit_code == 0
            and verify_run(root, record.run_id)["ok"]
        ):
            runs.append(run_dir)
    if not runs:
        return _guidance(
            "run_recovery",
            "Run attempts exist, but none is a completed integrity-verified execution.",
            [
                _action(
                    "inspect_failed_runs",
                    "Inspect failed or incomplete run records",
                    kind="command",
                    recommended=True,
                    command="smairt validate",
                ),
                _action(
                    "verify_runs",
                    "Verify integrity manifests for recorded runs",
                    kind="command",
                    command="smairt verify --json",
                ),
            ],
        )
    decisions = root / "analysis" / str(metadata["id"]) / "decisions.yaml"
    decision_records: list[object] = []
    if decisions.exists():
        payload = yaml.safe_load(decisions.read_text(encoding="utf-8")) or {}
        if isinstance(payload, dict) and isinstance(payload.get("decisions"), list):
            decision_records = payload["decisions"]
    if not decision_records:
        latest_run = runs[-1]
        return _guidance(
            "run_complete",
            f"{latest_run.name} completed and its provenance bundle was recorded.",
            [
                _action(
                    "interpret_run",
                    "Interpret the run and prepare a human decision",
                    kind="prompt",
                    recommended=True,
                    read=[
                        str(latest_run.relative_to(root)),
                        str((root / "analysis" / str(metadata["id"])).relative_to(root)),
                    ],
                    prompt=(
                        "Separate observations, derived results, interpretation, limitations, "
                        "and confounders; then ask me to ACCEPT, REVISE, ABANDON, or mark BLOCKED."
                    ),
                ),
                _action(
                    "record_decision",
                    "Record the human decision for this run",
                    kind="command",
                    requires_human=True,
                    command=(
                        f"smairt decision record --experiment {metadata['id']} "
                        f"--iteration {iteration_id} --run {latest_run.name} "
                        "--decision ACCEPT|REVISE|ABANDON|BLOCKED "
                        "--rationale '<rationale>' --decided-by '<contributor>'"
                    ),
                ),
                _action(
                    "review_run",
                    "Inspect the run bundle",
                    kind="read",
                    read=[str(latest_run.relative_to(root))],
                ),
            ],
        )
    if config.active.accepted_run:
        paper_guidance = _paper_guidance(root, config.active.accepted_run)
        if paper_guidance:
            return paper_guidance
    return _guidance(
        "decision_recorded",
        f"A research decision is recorded for {metadata['id']}.",
        [
            _action(
                "review_next_direction",
                "Review the decision and choose the next research direction",
                kind="human_choice",
                recommended=True,
                requires_human=True,
                read=[str(decisions.relative_to(root))],
            ),
            _action(
                "new_iteration",
                "Create a revised iteration",
                kind="command",
                command=f"smairt iteration new --experiment {metadata['id']} --from {iteration_id}",
            ),
            _action(
                "paper_evidence",
                "Review accepted evidence for the paper",
                kind="prompt",
                prompt=(
                    "Review accepted evidence and suggest whether any result belongs in the "
                    "paper manifest."
                ),
            ),
        ],
    )


def _paper_guidance(root: Path, accepted_run: str) -> dict[str, Any] | None:
    """Recommend evidence, claim, drafting, review, and build steps when ready."""
    try:
        evidence = [
            EvidenceCard.model_validate_json(path.read_text(encoding="utf-8"))
            for path in (root / "paper/evidence").glob("*.json")
        ]
        claims = [
            ClaimRecord.model_validate_json(path.read_text(encoding="utf-8"))
            for path in (root / "paper/claims").glob("*.json")
        ]
    except (OSError, ValueError):
        return _guidance(
            "paper_recovery",
            "Paper state contains a malformed evidence or claim record.",
            [
                _action(
                    "validate_paper_state",
                    "Inspect paper provenance errors",
                    kind="command",
                    recommended=True,
                    command="smairt validate",
                )
            ],
        )
    current = [
        item for item in evidence if item.run_id == accepted_run and item.status.value == "current"
    ]
    if not current:
        return _guidance(
            "evidence_review",
            f"{accepted_run} is accepted and ready for evidence review.",
            [
                _action(
                    "create_evidence_card",
                    "Review and freeze an evidence card",
                    kind="human_choice",
                    recommended=True,
                    requires_human=True,
                    command=f"smairt paper evidence review --run {accepted_run}",
                )
            ],
        )
    proposed = [claim for claim in claims if claim.status.value == "proposed"]
    approved = [claim for claim in claims if claim.status.value == "approved"]
    if proposed:
        claim_id = proposed[0].id
        return _guidance(
            "claim_review",
            f"{len(proposed)} proposed claim(s) require human review.",
            [
                _action(
                    "review_claims",
                    "Approve or reject proposed claims",
                    kind="human_choice",
                    recommended=True,
                    requires_human=True,
                    read=["paper/claims/"],
                    command=f"smairt paper claim approve {claim_id} --yes",
                )
            ],
        )
    if not approved:
        return _guidance(
            "claim_proposal",
            "Current evidence is reviewed but no claim is approved.",
            [
                _action(
                    "propose_claim",
                    "Propose a claim grounded in the evidence card",
                    kind="command",
                    recommended=True,
                    read=["paper/evidence/"],
                    command=(
                        "smairt paper claim propose --statement '<claim>' --evidence <evidence-id>"
                    ),
                    prompt=(
                        "Draft a bounded claim supported by the current evidence card, then "
                        "propose it with smairt paper claim propose."
                    ),
                )
            ],
        )
    manuscript = root / "paper/manuscript.md"
    if not manuscript.exists():
        return _guidance(
            "paper_ready",
            f"{len(approved)} claim(s) are approved; drafting may begin.",
            [
                _action(
                    "begin_paper",
                    "Begin the canonical Markdown manuscript",
                    kind="command",
                    recommended=True,
                    command="smairt paper begin --title '<title>'",
                )
            ],
        )
    sections_path = root / "paper/sections.yaml"
    sections = (yaml.safe_load(sections_path.read_text()) or {}).get("sections", {})
    drafts = [name for name, value in sections.items() if value.get("status") != "reviewed"]
    if drafts:
        return _guidance(
            "paper_drafting",
            "The canonical manuscript exists and contains draft sections.",
            [
                _action(
                    "draft_review_section",
                    f"Draft and review {drafts[0]}",
                    kind="prompt",
                    recommended=True,
                    read=["paper/manuscript.md", "paper/claims/"],
                )
            ],
        )
    return _guidance(
        "paper_reviewed",
        "All manuscript sections are explicitly reviewed.",
        [
            _action(
                "build_paper",
                "Build versioned Markdown and DOCX snapshots",
                kind="command",
                recommended=True,
                command="smairt paper build --format docx",
            )
        ],
    )


def _experiment(root: Path, identifier: str | None) -> Path | None:
    """Resolve the currently active experiment when an identifier is available."""
    return next((root / "experiments").glob(f"{identifier}_*"), None) if identifier else None


def _guidance(stage: str, completed: str, actions: list[dict[str, Any]]) -> dict[str, Any]:
    """Package a completed stage and bounded adaptive action list for Codex."""
    return {
        "stage": stage,
        "completed": completed,
        "recommended": next(
            (item for item in actions if item["recommended"]), actions[0] if actions else None
        ),
        "actions": actions[:4],
    }


def render_suggested_prompt(root: Path, guidance: dict[str, Any] | None = None) -> str:
    """Render the recommended action as a portable, bounded harness handoff."""
    payload = guidance or next_guidance(root)
    action = payload.get("recommended")
    if not isinstance(action, dict):
        return "Inspect this SMAIRT project and report why no next action is currently available."
    config = SmairtConfig.load(root / "smairt.yaml")
    lines = [
        f"SMAIRT project stage: {payload['stage']}",
        f"Objective: {action['label']}",
        f"Configured harness: {config.harness.active.value}",
    ]
    reads = action.get("read") or []
    if reads:
        lines.extend(["", "Read only the bounded starting context:"])
        lines.extend(f"- {path}" for path in reads)
    instruction = action.get("prompt")
    command = action.get("command")
    lines.extend(["", "Task:"])
    if instruction:
        lines.append(str(instruction))
    elif command:
        lines.append(
            f"Run `{command}`, inspect its result, and report the resulting project state."
        )
    else:
        lines.append("Review the listed state and help the researcher complete this action.")
    lines.extend(
        [
            "",
            "Follow the repository's SMAIRT and research conventions. Keep source-backed "
            "claims, inference, limitations, and evidence gaps distinct.",
            "Do not select hypotheses, accept evidence, approve claims, change safety policy, "
            "or cross another human decision gate without explicit researcher confirmation.",
        ]
    )
    return "\n".join(lines)
