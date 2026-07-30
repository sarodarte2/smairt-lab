"""Critical production-readiness scenarios for locks, recovery, runs, hooks, and safety."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
from pathlib import Path

import pytest
from pydantic import ValidationError

from smairt.diagnostics import doctor
from smairt.errors import IntegrityError, MutationConflictError, RecoveryRequiredError
from smairt.harnesses import ADAPTER_VERSION, harness_status, select_harness
from smairt.integrity import verify_run
from smairt.locking import ProjectMutationLock, break_lock, read_lock
from smairt.models import DataClassification, Decision, ReferenceRecord, RunStatus, SmairtConfig
from smairt.paper import accepted_runs
from smairt.project import validate_project
from smairt.references import add_reference, inspect_pdf
from smairt.research import create_experiment, record_decision
from smairt.runner import run_experiment
from smairt.safety import cached_repository_observation, refresh_repository_visibility
from smairt.scaffold import create_project
from smairt.transactions import (
    FileTransaction,
    complete_transaction,
    rollback_transaction,
    transaction_status,
)
from smairt.tui import _preflight_destination
from smairt.utils import sha256_text


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Create a contributor-confirmed local project for consequential tests."""
    root = tmp_path / "project"
    create_project(
        root,
        name="Production",
        author="Researcher",
        classification=DataClassification.UNPUBLISHED,
        initialize_git=False,
        confirm_contributor=True,
    )
    return root


def test_lock_conflict_stale_recovery_and_explicit_break(project: Path) -> None:
    """Distinguish live, stale, corrupt, and explicitly broken lock ownership."""
    with ProjectMutationLock(project, "outer"):
        assert read_lock(project)["process_alive"]
        with ProjectMutationLock(project, "nested"):
            assert read_lock(project)["owner"]["command"] == "outer"
    lock = project / ".smairt/locks/mutation.lock"
    lock.mkdir()
    (lock / "owner.json").write_text(
        json.dumps(
            {
                "host": socket.gethostname(),
                "pid": 999_999_999,
                "command": "dead",
                "contributor": None,
                "acquired_at": "2026-01-01T00:00:00Z",
                "token": "stale-owner-token",
            }
        )
    )
    with ProjectMutationLock(project, "recovered"):
        assert read_lock(project)["owner"]["command"] == "recovered"
    lock.mkdir()
    (lock / "owner.json").write_text("not-json")
    with pytest.raises(MutationConflictError):
        break_lock(project)
    assert break_lock(project, force=True)["broken"]


def test_lock_serializes_threads_in_the_same_process(project: Path) -> None:
    """Do not mistake a different worker thread for a reentrant lock acquisition."""
    first_entered = threading.Event()
    release_first = threading.Event()
    second_entered = threading.Event()

    def first() -> None:
        with ProjectMutationLock(project, "first thread"):
            first_entered.set()
            assert release_first.wait(timeout=2)

    def second() -> None:
        assert first_entered.wait(timeout=2)
        with ProjectMutationLock(project, "second thread"):
            second_entered.set()

    first_thread = threading.Thread(target=first)
    second_thread = threading.Thread(target=second)
    first_thread.start()
    second_thread.start()
    assert first_entered.wait(timeout=2)
    assert not second_entered.wait(timeout=0.05)
    release_first.set()
    first_thread.join(timeout=2)
    second_thread.join(timeout=2)
    assert second_entered.is_set()


def test_transactions_complete_rollback_and_recovery_gate(project: Path) -> None:
    """Recover partially applied state and block unrelated writers until resolution."""
    first = project / "state-a.txt"
    second = project / "state-b.txt"
    first.write_text("before")
    rollback = FileTransaction(project, "test rollback")
    rollback.stage_text(first, "after")
    rollback.stage_text(second, "created")
    first.write_text("after")
    second.write_text("created")
    rollback_record = {
        "schema_version": 1,
        "id": rollback.id,
        "command": "test rollback",
        "created_at": "2026-01-01T00:00:00Z",
        "status": "applying",
        "operations": rollback.operations,
    }
    (rollback.path / "transaction.json").write_text(json.dumps(rollback_record))
    rollback_transaction(project, rollback.id)
    assert first.read_text() == "before"
    assert not second.exists()

    transaction = FileTransaction(project, "test commit")
    transaction.stage_text(first, "after")
    record = transaction.commit()
    assert first.read_text() == "after"
    assert transaction_status(project)["ok"]
    with pytest.raises(RecoveryRequiredError, match="only incomplete"):
        rollback_transaction(project, str(record["id"]))

    pending = FileTransaction(project, "pending")
    pending.stage_text(first, "completed")
    metadata = {
        "schema_version": 1,
        "id": pending.id,
        "command": "pending",
        "created_at": "2026-01-01T00:00:00Z",
        "status": "prepared",
        "operations": pending.operations,
    }
    (pending.path / "transaction.json").write_text(json.dumps(metadata))
    with pytest.raises(RecoveryRequiredError), ProjectMutationLock(project, "unrelated"):
        pass
    complete_transaction(project, pending.id)
    assert first.read_text() == "completed"
    with pytest.raises(RecoveryRequiredError):
        complete_transaction(project, pending.id)
    empty = FileTransaction(project, "empty")
    with pytest.raises(ValueError, match="no operations"):
        empty.commit()
    with pytest.raises(ValueError, match="escapes"):
        empty.stage_text(project.parent / "outside", "unsafe")


def test_recovery_rejects_tampering_and_journal_path_escape(project: Path) -> None:
    """Never trust journal paths, staged bytes, backups, or divergent targets."""
    target = project / "target.txt"
    target.write_text("before")
    transaction = FileTransaction(project, "tamper")
    transaction.stage_text(target, "after")
    record = {
        "schema_version": 1,
        "id": transaction.id,
        "command": "tamper",
        "created_at": "2026-01-01T00:00:00Z",
        "status": "prepared",
        "operations": transaction.operations,
    }
    (transaction.path / "transaction.json").write_text(json.dumps(record))
    (transaction.path / "staged/0").write_text("modified")
    with pytest.raises(IntegrityError, match="integrity"):
        complete_transaction(project, transaction.id)

    transaction = FileTransaction(project, "escape")
    transaction.stage_text(target, "after")
    transaction.operations[0]["target"] = "../outside.txt"
    record["id"] = transaction.id
    record["operations"] = transaction.operations
    (transaction.path / "transaction.json").write_text(json.dumps(record))
    with pytest.raises(IntegrityError, match="safe relative"):
        complete_transaction(project, transaction.id)

    outside = project.parent / "outside-state.txt"
    outside.write_text("outside")
    linked = project / "linked-state.txt"
    linked.symlink_to(outside)
    transaction = FileTransaction(project, "symlink")
    with pytest.raises(ValueError, match="unsafe"):
        transaction.stage_text(linked, "changed")
    assert outside.read_text() == "outside"


def test_runner_records_nonzero_and_launch_failures(project: Path, monkeypatch) -> None:
    """Finalize every execution attempt and keep failed runs out of accepted evidence."""
    create_experiment(project, title="Runner", purpose="Test failure capture")
    failed = run_experiment(
        project,
        experiment_id="EXPERIMENT_001",
        iteration_id="ITERATION_001",
        command=[sys.executable, "-c", "raise SystemExit(7)"],
    )
    assert failed.status is RunStatus.FAILED
    assert failed.exit_code == 7
    assert (project / failed.manifest_path).exists()
    missing = run_experiment(
        project,
        experiment_id="EXPERIMENT_001",
        iteration_id="ITERATION_001",
        command=["definitely-not-a-real-executable"],
    )
    assert missing.status is RunStatus.FAILED
    assert missing.exit_code == 127
    assert "launch failure" in (project / missing.log_path).read_text()
    assert not any(item["code"] == "run.incomplete" for item in validate_project(project).findings)
    assert not list(project.rglob(".run.log.incomplete"))


def test_runner_redacts_command_credentials_everywhere(project: Path) -> None:
    """Keep credential-shaped arguments out of records, logs, and captured child output."""
    create_experiment(project, title="Secrets", purpose="Test provenance redaction")
    secret = "never-store-this-token"
    run = run_experiment(
        project,
        experiment_id="EXPERIMENT_001",
        iteration_id="ITERATION_001",
        command=[
            sys.executable,
            "-c",
            "import sys; print(sys.argv[2])",
            "--api-key",
            secret,
        ],
    )
    run_dir = project / run.results_directory
    assert secret not in (run_dir / "run.json").read_text()
    assert secret not in (run_dir / "run.log").read_text()
    assert "[REDACTED]" in (run_dir / "run.log").read_text()


def test_integrity_detects_artifacts_added_after_manifest(project: Path) -> None:
    """Treat unlisted post-run files as a mutation of the immutable run bundle."""
    create_experiment(project, title="Manifest", purpose="Test complete file-set locking")
    run = run_experiment(project, experiment_id="EXPERIMENT_001", iteration_id="ITERATION_001")
    (project / run.results_directory / "unlisted.txt").write_text("late artifact")
    report = verify_run(project, run.run_id)
    assert not report["ok"]
    assert any("unlisted artifact" in item["message"] for item in report["findings"])


def test_acceptance_requires_matching_integrity_locked_run(project: Path) -> None:
    """Reject scientifically accepted evidence when a locked run artifact changed."""
    create_experiment(project, title="Integrity", purpose="Test acceptance verification")
    run = run_experiment(
        project,
        experiment_id="EXPERIMENT_001",
        iteration_id="ITERATION_001",
    )
    (project / run.log_path).write_text("tampered after completion\n")
    with pytest.raises(ValueError, match="integrity-verified"):
        record_decision(
            project,
            experiment_id="EXPERIMENT_001",
            iteration_id="ITERATION_001",
            run_id=run.run_id,
            decision=Decision.ACCEPT,
            rationale="This must not be accepted.",
            decided_by="Researcher",
        )


def test_cline_hooks_and_harness_health(project: Path) -> None:
    """Execute upstream-shaped Cline hooks and expose manifest or mode damage."""
    select_harness(project, "cline")
    start = project / ".clinerules/hooks/TaskStart"
    payload = {
        "clineVersion": "3.0.0",
        "hookName": "TaskStart",
        "timestamp": "2026-01-01T00:00:00Z",
        "taskId": "task-1",
        "workspaceRoots": [str(project)],
        "userId": "user",
        "taskStart": {"taskMetadata": {"taskId": "task-1", "ulid": "01", "initialTask": "x"}},
    }
    result = subprocess.run(
        [str(start)],
        cwd=project,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": f"{Path(sys.executable).parent}:{os.environ['PATH']}"},
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["cancel"] is False
    assert "Objective:" in json.loads(result.stdout)["contextModification"]
    assert os.access(start, os.X_OK)
    assert (project / ".clinerules/hooks/PreCompact").exists()

    manifest = project / ".smairt/harnesses/cline.json"
    manifest.write_text("not-json")
    assert harness_status(project, "cline")["manifest_error"]
    manifest.unlink()
    select_harness(project, "zoo", backup_and_switch=True)
    (project / ".roomodes").write_text("customModes: wrong")
    assert harness_status(project, "zoo")["schema_errors"]
    assert SmairtConfig.load(project / "smairt.yaml").harness.adapter_version == ADAPTER_VERSION


def test_harness_switch_rejects_managed_directory_symlinks(project: Path, tmp_path: Path) -> None:
    """Never install agent rules or hooks through a project-directory symlink."""
    outside = tmp_path / "outside-harness"
    outside.mkdir()
    (project / ".roo").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        select_harness(project, "zoo")
    assert not list(outside.iterdir())


def test_harness_status_rejects_unsafe_manifest_paths_without_crashing(project: Path) -> None:
    """Surface malicious or corrupt managed paths as harness health errors."""
    manifest = project / ".smairt/harnesses/codex.json"
    payload = json.loads(manifest.read_text())
    payload["files"]["../outside"] = "0" * 64
    manifest.write_text(json.dumps(payload))
    status = harness_status(project, "codex")
    assert status["manifest_error"]


def test_visibility_refresh_cache_and_offline_status(project: Path, monkeypatch) -> None:
    """Cache one explicit observation and preserve stable failure reasons."""
    calls: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        output = "git@github.com:org/repo.git\n" if command[0] == "git" else "PRIVATE\n"
        return subprocess.CompletedProcess(command, 0, stdout=output, stderr="")

    monkeypatch.setattr("smairt.safety.subprocess.run", fake_run)
    monkeypatch.setattr("smairt.safety.shutil.which", lambda command: f"/usr/bin/{command}")
    refreshed = refresh_repository_visibility(project)
    assert refreshed["visibility"] == "private"
    assert len(calls) == 2
    calls.clear()
    assert cached_repository_observation(project)["visibility"] == "private"
    assert not calls

    monkeypatch.setattr("smairt.safety.shutil.which", lambda command: None)
    failed = refresh_repository_visibility(project)
    assert failed["status"] == "missing_cli"
    assert failed["visibility"] == "unknown"


def test_pdf_and_schema_edge_cases(project: Path, tmp_path: Path) -> None:
    """Reject empty PDFs, unsafe paths, extra fields, and duplicate destinations."""
    empty = tmp_path / "empty.pdf"
    empty.write_bytes(b"")
    with pytest.raises(ValueError, match="empty"):
        inspect_pdf(empty)
    corrupt = tmp_path / "corrupt.pdf"
    corrupt.write_bytes(b"not a pdf")
    with pytest.raises(ValueError, match="corrupt"):
        inspect_pdf(corrupt)
    with pytest.raises(ValidationError):
        ReferenceRecord.model_validate(
            {
                "id": "bad/id",
                "title": "x",
                "local_path": "../escape.pdf",
                "sha256": "0" * 64,
                "unexpected": True,
            }
        )
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\n%%EOF")
    add_reference(project, source, title="Unique", year=2026)
    with pytest.raises(ValueError, match="already indexed"):
        add_reference(project, source, title="Unique", year=2026)


def test_doctor_and_terminal_preflight_stay_offline(project: Path) -> None:
    """Keep doctor offline and reject unsafe terminal-wizard destinations."""
    report = doctor(project)
    assert report["network_accessed"] is False
    assert report["schema_compatible"]

    occupied = project.parent / "small"
    occupied.mkdir()
    (occupied / "notes.txt").write_text("keep")
    with pytest.raises(FileExistsError, match="contains files"):
        _preflight_destination(occupied, allow_existing=False)


def test_existing_checkout_scaffold_rejects_symlinks_and_unmanaged_targets(
    tmp_path: Path,
) -> None:
    """Preserve existing work and refuse generated writes through directory symlinks."""
    outside = tmp_path / "outside"
    outside.mkdir()
    linked = tmp_path / "linked"
    linked.mkdir()
    (linked / ".git").mkdir()
    (linked / "docs").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        create_project(
            linked,
            name="Linked",
            author="Researcher",
            classification=DataClassification.UNPUBLISHED,
            initialize_git=False,
        )
    assert not list(outside.iterdir())

    conflicting = tmp_path / "conflicting"
    conflicting.mkdir()
    (conflicting / ".git").mkdir()
    readme = conflicting / "AGENTS.md"
    readme.write_text("laboratory-owned instructions\n")
    with pytest.raises(FileExistsError, match="unmanaged scaffold targets"):
        create_project(
            conflicting,
            name="Conflict",
            author="Researcher",
            classification=DataClassification.UNPUBLISHED,
            initialize_git=False,
        )
    assert readme.read_text() == "laboratory-owned instructions\n"
    assert not (conflicting / "smairt.yaml").exists()


def test_runner_preserves_reserve_digests_when_child_mutates_config(project: Path) -> None:
    """Record pre-run config digests even if the child rewrites config.yaml."""
    create_experiment(project, title="Digest", purpose="Test reserve provenance")
    iteration = project / "experiments/EXPERIMENT_001_digest/iterations/ITERATION_001"
    before = (iteration / "config.yaml").read_text()
    run = run_experiment(
        project,
        experiment_id="EXPERIMENT_001",
        iteration_id="ITERATION_001",
        command=[
            sys.executable,
            "-c",
            ("from pathlib import Path\nPath('config.yaml').write_text('seed: mutated\\n')\n"),
        ],
    )
    assert run.config_sha256 is not None
    assert run.config_sha256 == sha256_text(before)
    assert (project / run.results_directory / "config.snapshot.yaml").read_text() == before
    assert run.environment.get("input_drift_after_run", {}).get("config_sha256")


def test_symlink_artifact_fails_finalize_and_validate_flags_missing_manifest(
    project: Path,
) -> None:
    """Do not leave a healthy completed run when the integrity manifest cannot be built."""
    create_experiment(project, title="Symlink", purpose="Test finalize ordering")
    target = project / "outside-target.txt"
    target.write_text("payload\n")
    with pytest.raises(ValueError, match="symlink"):
        run_experiment(
            project,
            experiment_id="EXPERIMENT_001",
            iteration_id="ITERATION_001",
            command=[
                sys.executable,
                "-c",
                (
                    "import os\n"
                    "from pathlib import Path\n"
                    f"Path(os.environ['SMAIRT_RESULTS_DIR'], 'link').symlink_to({str(target)!r})\n"
                ),
            ],
        )
    run_dirs = list((project / "results").glob("EXPERIMENT_001/ITERATION_001/RUN_*"))
    assert len(run_dirs) == 1
    run_json = json.loads((run_dirs[0] / "run.json").read_text())
    assert run_json["status"] == "failed"
    assert not (run_dirs[0] / "manifest.json").exists()
    findings = validate_project(project).findings
    assert any(item["code"] == "run.manifest_missing" for item in findings)


def test_accepted_runs_require_decision_backed_selection(project: Path) -> None:
    """Reject forged selection.yaml files that lack an ACCEPT decision record."""
    create_experiment(project, title="Selection", purpose="Test acceptance consistency")
    run = run_experiment(project, experiment_id="EXPERIMENT_001", iteration_id="ITERATION_001")
    analysis = project / "analysis/EXPERIMENT_001"
    analysis.mkdir(parents=True, exist_ok=True)
    (analysis / "selection.yaml").write_text(
        "experiment_id: EXPERIMENT_001\n"
        "iteration_id: ITERATION_001\n"
        f"run_id: {run.run_id}\n"
        "status: ACCEPTED\n"
    )
    with pytest.raises(ValueError, match="decision record"):
        accepted_runs(project)
    record_decision(
        project,
        experiment_id="EXPERIMENT_001",
        iteration_id="ITERATION_001",
        run_id=run.run_id,
        decision=Decision.ACCEPT,
        rationale="Fixture acceptance for selection consistency.",
        decided_by="Researcher",
    )
    assert run.run_id in accepted_runs(project)
