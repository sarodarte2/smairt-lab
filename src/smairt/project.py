"""Project discovery, status, context selection, and policy validation."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import yaml

from smairt.code_quality import validate_code
from smairt.locking import mutating
from smairt.model_policy import recommend_model
from smairt.models import Decision, RunRecord, RunStatus, SmairtConfig
from smairt.provenance import require_contributor, stage_event
from smairt.transactions import FileTransaction
from smairt.utils import ensure_no_symlink, sha256_file, write_json

PROHIBITED_SUFFIXES = {
    ".fast5",
    ".pod5",
    ".fastq",
    ".fq",
    ".bam",
    ".cram",
    ".pem",
    ".key",
    ".p12",
}
PROHIBITED_NAMES = {".env", "credentials.json", "secrets.json", "secrets.yaml"}


def find_project(start: Path | None = None) -> Path:
    """Find the nearest project without crossing an enclosing Git worktree.

    A broad directory such as ``~/Documents`` can itself contain a SMAIRT
    project.  A nested, unrelated Git checkout must not silently inherit that
    ancestor project.  Inside a Git worktree, its top-level directory is
    therefore the final discovery candidate.  Plain project subdirectories
    continue to use normal nearest-ancestor discovery.
    """
    current = (start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent
    candidates = (current, *current.parents)
    boundary: Path | None = None
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=current,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        result = None
    if result is not None and result.returncode == 0 and result.stdout.strip():
        boundary = Path(result.stdout.strip()).resolve()
    for candidate in candidates:
        if (candidate / "smairt.yaml").exists():
            return candidate
        if boundary is not None and candidate == boundary:
            break
    raise FileNotFoundError("No smairt.yaml found in this directory or its parents")


@mutating("project identity update")
def update_project_identity(
    root: Path,
    *,
    name: str,
    author: str,
    question: str | None,
    description: str | None,
) -> SmairtConfig:
    """Update only researcher-facing identity fields against the latest config state."""
    contributor = require_contributor(root)
    config = SmairtConfig.load(root / "smairt.yaml").model_copy(deep=True)
    config.project.name = name
    config.project.author = author
    config.project.question = question
    config.project.description = description
    rendered = config.to_yaml()
    SmairtConfig.model_validate(yaml.safe_load(rendered))
    transaction = FileTransaction(root, "project identity update")
    transaction.stage_text(root / "smairt.yaml", rendered)
    stage_event(
        root,
        transaction,
        "project.identity.updated",
        artifact_ids=["smairt.yaml"],
        details={"contributor": contributor.id},
    )
    transaction.commit()
    return config


@dataclass
class ValidationReport:
    """Collect compatibility fields and structured findings from project checks."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checks: dict[str, bool] = field(default_factory=dict)
    findings: list[dict[str, str]] = field(default_factory=list)
    readiness: dict[str, bool] = field(default_factory=dict)

    def add(self, severity: str, code: str, artifact: str, message: str) -> None:
        """Add one finding and mirror it into legacy error or warning lists."""
        remediation = _finding_remediation(code, artifact)
        finding = {
            "severity": severity,
            "code": code,
            "title": code.replace(".", " ").replace("_", " ").title(),
            "artifact": artifact,
            "message": message,
            "summary": message,
            "remediation": remediation,
        }
        self.findings.append(finding)
        (self.errors if severity == "error" else self.warnings).append(message)

    @property
    def ok(self) -> bool:
        """Return true when no error-severity finding prevents safe progress."""
        return not self.errors

    def as_dict(self) -> dict[str, object]:
        """Convert the report into the stable JSON-facing validation contract."""
        return {
            "ok": self.ok,
            "checks": self.checks,
            "errors": self.errors,
            "warnings": self.warnings,
            "findings": self.findings,
            "readiness": self.readiness,
        }


def _finding_remediation(code: str, artifact: str) -> str:
    """Map stable finding families to concise, non-destructive next actions."""
    if code.startswith(("git.credentials", "git.protected")):
        return (
            "Remove the protected content from the Git index, rotate exposed keys, "
            "then validate again."
        )
    if code.startswith("project.required_files"):
        return (
            "Run Health > Preview safe SMAIRT-managed repairs; do not overwrite "
            "user-authored files."
        )
    if code.startswith("references"):
        return (
            f"Review {artifact} through SMAIRT References, correct the record, then validate again."
        )
    if code.startswith("code."):
        return (
            "Open the reported code artifact, address the readability or traceability "
            "issue, and rerun validation."
        )
    if code.startswith("run."):
        return (
            "Preserve the run bundle and use SMAIRT recovery, correction, or a new "
            "iteration as appropriate."
        )
    if code.startswith(("background.", "proposal.", "hypothesis.")):
        return (
            "Use `smairt next` for the bounded workflow action; a human must cross "
            "scientific decision gates."
        )
    return (
        f"Inspect {artifact}, use `smairt doctor` for context, and rerun validation "
        "after correction."
    )


def _git_files(root: Path, staged: bool) -> list[str]:
    """List tracked or staged paths, rejecting an unknown Git safety state."""
    command = ["git", "diff", "--cached", "--name-only"] if staged else ["git", "ls-files"]
    try:
        result = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise RuntimeError("Git could not scan protected paths") from exc
    if result.returncode != 0:
        raise RuntimeError("Git could not scan protected paths")
    return result.stdout.splitlines()


def is_prohibited(relative: str) -> bool:
    """Return whether a repository path violates generated data-safety policy."""
    path = Path(relative)
    lower = relative.lower()
    return (
        path.name.lower() in PROHIBITED_NAMES
        or path.suffix.lower() in PROHIBITED_SUFFIXES
        or lower.startswith(("references/pdfs/", "data/raw/", "data/local/", ".smairt/local/"))
        or path.name.lower().startswith("credentials")
        or path.name.lower().startswith("secrets")
    )


def _staged_secret_paths(root: Path) -> list[str]:
    """Return staged files with credential assignments without exposing values."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--no-ext-diff", "--unified=0"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise RuntimeError("Git could not scan staged credential content") from exc
    if result.returncode != 0:
        raise RuntimeError("Git could not scan staged credential content")
    current = "unknown"
    findings: set[str] = set()
    assignment = re.compile(
        r"(?i)(?:OPENALEX_API_KEY|ZOTERO_API_KEY|api[_-]?key|access[_-]?token|password|secret)"
        r"\s*[:=]\s*['\"]?([^\s'\"]+)"
    )
    placeholders = {"", "none", "null", "changeme", "your-key", "<key>", "${value}"}
    for line in result.stdout.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
        if not line.startswith("+") or line.startswith("+++"):
            continue
        match = assignment.search(line[1:])
        if match and match.group(1).strip().lower() not in placeholders:
            findings.add(current)
    return sorted(findings)


def validate_project(
    root: Path, *, staged: bool = False, tool_input: bool = False
) -> ValidationReport:
    """Validate project structure, safety, research links, code, and paper provenance."""
    report = ValidationReport()
    try:
        config = SmairtConfig.load(root / "smairt.yaml")
        report.checks["project_contract"] = True
    except Exception as exc:
        report.add("error", "project.contract", "smairt.yaml", f"Invalid project contract: {exc}")
        report.checks["project_contract"] = False
        return report

    required = ["AGENTS.md", "references/index.yaml", "prompts/CODE_CONVENTIONS.md"]
    missing = [item for item in required if not (root / item).exists()]
    report.checks["required_files"] = not missing
    if missing:
        report.add(
            "error", "project.required_files", ".", f"Missing required files: {', '.join(missing)}"
        )

    if config.git.enabled:
        if not (root / ".git").exists():
            report.checks["git_safety"] = False
            report.add(
                "error",
                "git.repository_missing",
                ".git",
                "Git is enabled in smairt.yaml but this checkout is not a repository",
            )
        else:
            try:
                prohibited = [item for item in _git_files(root, staged) if is_prohibited(item)]
            except RuntimeError as exc:
                report.checks["git_safety"] = False
                report.add("error", "git.scan_failed", ".git", str(exc))
            else:
                report.checks["git_safety"] = not prohibited
                if prohibited:
                    report.add(
                        "error",
                        "git.protected",
                        ".git",
                        f"Protected files are tracked/staged: {', '.join(prohibited)}",
                    )
                if staged:
                    try:
                        secret_paths = _staged_secret_paths(root)
                    except RuntimeError as exc:
                        report.checks["credential_scan"] = False
                        report.add("error", "git.credential_scan_failed", ".git", str(exc))
                    else:
                        report.checks["credential_scan"] = not secret_paths
                        if secret_paths:
                            report.add(
                                "error",
                                "git.credentials",
                                ".git",
                                "Possible credential values are staged in: "
                                + ", ".join(secret_paths)
                                + "; values were redacted",
                            )
    else:
        report.checks["git_safety"] = True

    from smairt.safety import safety_policy_findings

    for finding in safety_policy_findings(root, staged=staged):
        report.add(
            finding["severity"],
            finding["code"],
            finding["artifact"],
            "Project safety policy requires attention",
        )

    try:
        from smairt.references import load_index

        records = load_index(root)
        for label, values in (
            ("ID", [item.id for item in records]),
            ("citation key", [item.citation_key for item in records if item.citation_key]),
            ("DOI", [item.doi for item in records if item.doi]),
            ("destination", [item.local_path for item in records]),
        ):
            if len(set(values)) != len(values):
                raise ValueError(f"duplicate reference {label}")
        report.checks["reference_index"] = True
    except Exception as exc:
        report.checks["reference_index"] = False
        report.add(
            "error", "references.parse", "references/index.yaml", f"Invalid reference index: {exc}"
        )

    for finding in validate_code(root):
        report.add(finding["severity"], finding["code"], finding["artifact"], finding["message"])
    report.checks["code_readability"] = not any(
        item["severity"] == "error" and item["code"].startswith("code.") for item in report.findings
    )

    from smairt.research import (
        find_hypothesis,
        validate_background,
        validate_hypothesis,
        validate_proposal_set,
    )

    background_path = root / "background/initial_background.md"
    if (
        background_path.exists()
        and background_path.read_text().strip() != "# Initial Background\n\nStatus: DRAFT"
    ):
        for message in validate_background(root):
            report.add(
                "warning", "background.incomplete", str(background_path.relative_to(root)), message
            )
    proposals = sorted((root / "hypotheses/proposals").glob("PROPOSAL_SET_*.md"))
    if proposals:
        for message in validate_proposal_set(proposals[-1]):
            report.add(
                "warning", "proposal.incomplete", str(proposals[-1].relative_to(root)), message
            )
    if config.active.hypothesis:
        try:
            hypothesis_path = find_hypothesis(root, config.active.hypothesis)
        except FileNotFoundError:
            report.add(
                "error", "hypothesis.link", "smairt.yaml", "Active hypothesis file is missing"
            )
        else:
            for message in validate_hypothesis(hypothesis_path):
                report.add(
                    "warning",
                    "hypothesis.incomplete",
                    str(hypothesis_path.relative_to(root)),
                    message,
                )

    from smairt.science import validate_protocol

    for experiment_path in sorted((root / "experiments").glob("EXPERIMENT_*")):
        metadata_path = experiment_path / "experiment.yaml"
        metadata = yaml.safe_load(metadata_path.read_text()) if metadata_path.exists() else {}
        for iteration_path in sorted((experiment_path / "iterations").glob("ITERATION_*")):
            protocol_path = iteration_path / "protocol.yaml"
            if metadata.get("protocol_required"):
                for message in validate_protocol(protocol_path):
                    report.add(
                        "error",
                        "protocol.incomplete",
                        str(protocol_path.relative_to(root)),
                        message,
                    )
            elif config.schema_version >= 8 and not protocol_path.exists():
                report.add(
                    "warning",
                    "protocol.legacy",
                    str(iteration_path.relative_to(root)),
                    "Legacy iteration has no schema-8 scientific protocol",
                )

    # Run records are the bridge between executed code and later scientific claims.
    # Validate them without executing or importing any researcher-authored code.
    for run_path in sorted((root / "results").glob("EXPERIMENT_*/ITERATION_*/RUN_*/run.json")):
        relative = str(run_path.relative_to(root))
        try:
            run_record = RunRecord.model_validate_json(run_path.read_text(encoding="utf-8"))
        except Exception as exc:
            report.add("error", "run.record", relative, f"Invalid run record: {exc}")
            continue
        if run_record.status is RunStatus.STARTED:
            report.add(
                "error",
                "run.incomplete",
                relative,
                "Run was reserved but never finalized; do not use it as evidence",
            )
        elif run_record.status in {
            RunStatus.COMPLETED,
            RunStatus.FAILED,
            RunStatus.INTERRUPTED,
        }:
            manifest_path = run_path.parent / "manifest.json"
            lock_path = root / ".smairt/run-manifests" / f"{run_record.run_id}.json"
            if not manifest_path.is_file() or not lock_path.is_file():
                report.add(
                    "error",
                    "run.manifest_missing",
                    relative,
                    "Terminal run is missing its integrity manifest or lock",
                )
        for field_name, recorded_path in (
            ("log", run_record.log_path),
            ("results", run_record.results_directory),
        ):
            if not (root / recorded_path).exists():
                report.add(
                    "error",
                    f"run.{field_name}_missing",
                    relative,
                    f"Recorded {field_name} path does not exist: {recorded_path}",
                )

    recorded_directories = {path.parent for path in (root / "results").glob("*/*/*/run.json")}
    for run_dir in sorted((root / "results").glob("EXPERIMENT_*/*/RUN_*")):
        if run_dir.is_dir() and run_dir not in recorded_directories:
            report.add(
                "error",
                "run.record_missing",
                str(run_dir.relative_to(root)),
                "Run directory has no durable run record",
            )

    from smairt.integrity import verify_run

    integrity = verify_run(root)
    report.checks["run_integrity"] = bool(integrity["ok"])
    for finding in cast(list[dict[str, Any]], integrity["findings"]):
        report.add(
            "error",
            "run.artifact_mutated",
            str(finding["run_id"]),
            str(finding["message"]),
        )
    # Decisions are human gates. A dangling decision would make the audit trail
    # appear stronger than the evidence, so broken links are hard errors.
    for decisions_path in sorted((root / "analysis").glob("EXPERIMENT_*/decisions.yaml")):
        payload = yaml.safe_load(decisions_path.read_text()) or {}
        for decision in payload.get("decisions", []):
            run_id = str(decision.get("run_id", ""))
            iteration_id = str(decision.get("iteration_id", ""))
            experiment_id = decisions_path.parent.name
            try:
                Decision(str(decision.get("decision")))
                from smairt.utils import validate_identifier

                validate_identifier(run_id, label="run ID")
                validate_identifier(iteration_id, label="iteration ID")
            except ValueError:
                report.add(
                    "error",
                    "decision.value",
                    str(decisions_path.relative_to(root)),
                    f"Invalid decision record for run: {run_id or '[missing]'}",
                )
                continue
            run_path = root / "results" / experiment_id / iteration_id / run_id / "run.json"
            try:
                record = RunRecord.model_validate_json(run_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                report.add(
                    "error",
                    "decision.run_link",
                    str(decisions_path.relative_to(root)),
                    f"Decision references missing or invalid run: {run_id}",
                )
                continue
            if (record.experiment_id, record.iteration_id, record.run_id) != (
                experiment_id,
                iteration_id,
                run_id,
            ):
                report.add(
                    "error",
                    "decision.run_link",
                    str(decisions_path.relative_to(root)),
                    f"Decision relationships do not match run record: {run_id}",
                )

    from smairt.paper import validate_paper

    for message in validate_paper(root):
        report.add("error", "paper.provenance", "paper/manifest.yaml", message)

    if not config.project.question:
        report.add(
            "warning",
            "project.question",
            "smairt.yaml",
            "Initial research question is not specified",
        )
    if config.data.classification.value == "controlled":
        report.add(
            "warning",
            "data.controlled",
            "smairt.yaml",
            "Controlled-data storage enforcement is not implemented in v1",
        )

    if tool_input and not sys.stdin.isatty():
        payload = sys.stdin.read()
        if any(token in payload.lower() for token in ("data/raw/", ".fast5", ".env", "api_key")):
            report.add(
                "error",
                "tool.protected_input",
                "stdin",
                "Codex tool input may access protected data or secrets",
            )
    report.readiness = _readiness(root, config)
    return report


def _readiness(root: Path, config: SmairtConfig) -> dict[str, bool]:
    """Summarize whether each workflow stage is structurally ready to advance."""
    background = root / "background/initial_background.md"
    from smairt.research import validate_background

    background_ready = background.exists() and not validate_background(root)
    proposals = sorted((root / "hypotheses/proposals").glob("PROPOSAL_SET_*.md"))
    proposal_ready = False
    if proposals:
        from smairt.research import validate_proposal_set

        proposal_ready = not validate_proposal_set(proposals[-1])
    hypothesis_ready = False
    if config.active.hypothesis:
        from smairt.research import find_hypothesis, validate_hypothesis

        try:
            hypothesis_ready = not validate_hypothesis(
                find_hypothesis(root, config.active.hypothesis)
            )
        except FileNotFoundError:
            hypothesis_ready = False
    return {
        "background": background_ready,
        "proposal_set": proposal_ready,
        "hypothesis": hypothesis_ready,
        "experiment": bool(config.active.experiment),
        "accepted_evidence": bool(config.active.accepted_run),
    }


def status(root: Path) -> dict[str, Any]:
    """Return compact project state, counts, validation, readiness, and guidance."""
    config = SmairtConfig.load(root / "smairt.yaml")
    report = validate_project(root)
    proposals = sorted((root / "hypotheses/proposals").glob("PROPOSAL_SET_*.md"))
    hypotheses = [
        path
        for path in sorted((root / "hypotheses").glob("HYPOTHESIS_*.md"))
        if path.name != "HYPOTHESIS_TEMPLATE.md"
    ]
    experiments = sorted((root / "experiments").glob("EXPERIMENT_*"))
    from smairt.guidance import next_guidance

    guidance = next_guidance(root)
    return {
        "project": config.project.model_dump(mode="json"),
        "data_classification": config.data.classification.value,
        "environment": config.environment.model_dump(mode="json", exclude_none=True),
        "schema_version": config.schema_version,
        "safety_mode": config.safety_mode,
        "active_contributor": config.active_contributor,
        "harness": config.harness.model_dump(mode="json"),
        "active": config.active.model_dump(mode="json", exclude_none=True),
        "counts": {
            "proposal_sets": len(proposals),
            "hypotheses": len(hypotheses),
            "experiments": len(experiments),
        },
        "validation": report.as_dict(),
        "stage": guidance["stage"],
        "readiness": report.readiness,
        "guidance": guidance,
    }


CONTEXT_MAP = {
    "planning": [
        "prompts/RESEARCH_CONVENTIONS.md",
        "plans/README.md",
        "background/initial_background.md",
    ],
    "code": [
        "prompts/CODE_CONVENTIONS.md",
        "prompts/KNOWN_PATTERNS.md",
    ],
    "run": [
        "prompts/CODE_CONVENTIONS.md",
        "prompts/RESEARCH_CONVENTIONS.md",
    ],
    "interpretation": [
        "prompts/INTERPRETATION_CONVENTIONS.md",
        "prompts/intellectual_contribution.md",
    ],
    "paper": [
        "paper/README.md",
        "paper/manifest.yaml",
        "prompts/INTERPRETATION_CONVENTIONS.md",
    ],
    "review": [
        "prompts/RESEARCH_CONVENTIONS.md",
        "prompts/INTERPRETATION_CONVENTIONS.md",
        "plans/README.md",
    ],
}


def context(
    root: Path, task: str, token_budget: int = 8000, target: str | None = None
) -> dict[str, object]:
    """Select the smallest initial file set needed for a particular research task."""
    if task not in CONTEXT_MAP:
        raise ValueError(f"Unknown task {task!r}; choose {', '.join(CONTEXT_MAP)}")
    review_target: str | None = None
    if target is not None:
        if task != "review":
            raise ValueError("--target is supported only with --task review")
        target_path = ensure_no_symlink(root, root / target)
        if not target_path.is_file():
            raise ValueError("review target must be an existing project file")
        relative_target = str(target_path.relative_to(root.resolve()))
        if is_prohibited(relative_target):
            raise ValueError("review target is protected by SMAIRT data policy")
        if target_path.suffix.lower() not in {".md", ".json", ".yaml", ".yml", ".py", ".r", ".txt"}:
            raise ValueError("review target must be a bounded textual research artifact")
        if target_path.stat().st_size > 1024 * 1024:
            raise ValueError("review target exceeds the 1 MiB context safety bound")
        review_target = relative_target
    current = status(root)
    included = []
    deferred = []
    status_tokens = max(1, len(json.dumps(current, default=str)) // 4)
    used = status_tokens
    candidates: list[tuple[int, str, str]] = [
        (30, relative, f"default {task} context") for relative in CONTEXT_MAP[task]
    ]
    if review_target:
        candidates.append((0, review_target, "explicit adversarial-review target"))
    config = SmairtConfig.load(root / "smairt.yaml")
    if config.active.hypothesis:
        hypothesis = next((root / "hypotheses").glob(f"{config.active.hypothesis}_*.md"), None)
        if hypothesis:
            candidates.append((5, str(hypothesis.relative_to(root)), "active hypothesis"))
    if config.active.experiment and config.active.iteration:
        experiment = next((root / "experiments").glob(f"{config.active.experiment}_*"), None)
        if experiment:
            iteration = experiment / "iterations" / config.active.iteration
            for path in sorted(iteration.glob("*")):
                if path.is_file() and path.suffix in {".py", ".yaml", ".md"}:
                    candidates.append((10, str(path.relative_to(root)), "active iteration"))
    if task in {"interpretation", "paper", "review"}:
        for path in sorted((root / "paper/evidence").glob("*.json")):
            candidates.append((12, str(path.relative_to(root)), "current paper evidence"))
        for path in sorted((root / "paper/claims").glob("*.json")):
            candidates.append((14, str(path.relative_to(root)), "paper claim"))
    from smairt.summaries import list_summaries

    canonical_ids = {
        json.loads(path.read_text()).get("summary_id")
        for path in (root / "summaries/canonical").glob("*.json")
    }
    for summary in list_summaries(root):
        if summary["id"] in canonical_ids and summary["fresh"]:
            candidates.append((8, str(summary["artifact_path"]), "fresh canonical summary"))
    seen: set[str] = set()
    for _, relative, reason in sorted(candidates):
        if relative in seen:
            continue
        seen.add(relative)
        path = root / relative
        if not path.exists():
            continue
        estimated = max(1, len(path.read_text(encoding="utf-8", errors="replace")) // 4)
        item = {
            "path": relative,
            "estimated_tokens": estimated,
            "reason": reason,
            "sha256": sha256_file(path),
        }
        if used + estimated <= token_budget:
            included.append(item)
            used += estimated
        else:
            deferred.append({**item, "reason": "token budget exceeded"})
    payload: dict[str, object] = {
        "task": task,
        "status": current,
        "token_budget": token_budget,
        "estimated_tokens": used,
        "status_estimated_tokens": status_tokens,
        "estimated_cost": None,
        "model_recommendation": recommend_model(root, task),
        "read": [item["path"] for item in included],
        "included": included,
        "deferred": deferred,
        "rule": "Read only these files initially; load logs, PDFs, and older iterations on demand.",
    }
    if task == "review":
        payload["review_target"] = review_target or "current active research state"
        payload["review_rubric"] = [
            "strongest objection",
            "unsupported assumptions",
            "alternative explanations",
            "missing controls or falsifiers",
            "provenance and citation gaps",
            "severity and confidence",
            "smallest useful follow-up test",
        ]
        payload["mutation_allowed"] = False
    return payload


def save_context_capsule(root: Path, payload: dict[str, object]) -> Path:
    """Save a disposable context selection under the Git-ignored local state tree."""
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    path = root / ".smairt/local/context" / f"{payload['task']}-{stamp}.json"
    write_json(path, payload)
    return path
