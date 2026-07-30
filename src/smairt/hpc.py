"""Optional, typed Slurm submission and reconciliation."""

from __future__ import annotations

import re
import shlex
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

from smairt.integrity import build_manifest
from smairt.local_setup import selected_slurm_profile
from smairt.locking import ProjectMutationLock
from smairt.models import (
    ComputeJobRecord,
    ComputeJobStatus,
    ComputeMode,
    ComputeResources,
    RunRecord,
    RunStatus,
    SmairtConfig,
    utc_now,
)
from smairt.runner import _git_capture, _resolved_entrypoint, _safe_snapshot, _sanitized_command
from smairt.science import validate_protocol
from smairt.utils import (
    atomic_write,
    atomic_write_bytes,
    ensure_no_symlink,
    sha256_file,
    write_json,
)


def _experiment(root: Path, experiment_id: str) -> Path:
    matches = list((root / "experiments").glob(f"{experiment_id}_*"))
    if len(matches) != 1:
        raise FileNotFoundError(f"Experiment {experiment_id} not found or ambiguous")
    return ensure_no_symlink(root, matches[0])


def _scheduler_args(resources: ComputeResources) -> list[str]:
    hours, minutes = divmod(resources.wall_minutes, 60)
    values = [
        "--nodes",
        str(resources.nodes),
        "--cpus-per-task",
        str(resources.cpus),
        "--mem",
        f"{resources.memory_mib}M",
        "--time",
        f"{hours:02d}:{minutes:02d}:00",
    ]
    for flag, value in (
        ("--partition", resources.partition),
        ("--account", resources.account),
        ("--qos", resources.qos),
    ):
        if value:
            values.extend((flag, value))
    if resources.gpus:
        values.extend(("--gpus", str(resources.gpus)))
    return values


def _run_scheduler(profile_mode: ComputeMode, host: str | None, arguments: list[str]) -> str:
    command = arguments
    if profile_mode is ComputeMode.SSH:
        if not host:
            raise ValueError("SSH Slurm profile has no host alias")
        command = [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=yes",
            host,
            shlex.join(arguments),
        ]
    result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=30)
    if result.returncode != 0:
        detail = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "no detail"
        raise RuntimeError(f"Slurm command failed: {detail}")
    return result.stdout.strip()


def submit_slurm(
    root: Path,
    *,
    experiment_id: str,
    iteration_id: str,
    command: list[str] | None,
    resources: ComputeResources,
) -> ComputeJobRecord:
    """Reserve a run and submit a constrained batch job without waiting."""
    profile_name, profile = selected_slurm_profile()
    experiment = _experiment(root, experiment_id)
    metadata = yaml.safe_load((experiment / "experiment.yaml").read_text()) or {}
    iteration = ensure_no_symlink(root, experiment / "iterations" / iteration_id)
    if not iteration.is_dir():
        raise FileNotFoundError(iteration)
    protocol = iteration / "protocol.yaml"
    if metadata.get("protocol_required"):
        errors = validate_protocol(protocol)
        if errors:
            raise ValueError("Scientific protocol is incomplete: " + "; ".join(errors))
    original = list(command or [sys.executable, str(metadata.get("entrypoint", "run.py"))])
    recorded, secrets = _sanitized_command(original)
    if secrets:
        raise ValueError("Slurm commands cannot contain credential-shaped arguments")
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    run_id = f"RUN_{timestamp}"
    run_dir = root / "results" / experiment_id / iteration_id / run_id
    artifacts = run_dir / "artifacts"
    figures = run_dir / "figures"
    project_slug = SmairtConfig.load(root / "smairt.yaml").project.slug
    remote_dir = f"{profile.remote_root}/{project_slug}/{run_id}"
    execution_dir = str(iteration)
    execution_root = str(root)
    output_dir = str(artifacts)
    figure_dir = str(figures)
    log_path = str(run_dir / "run.log")
    if profile.mode is ComputeMode.SSH:
        execution_root = remote_dir
        execution_dir = f"{remote_dir}/iteration"
        output_dir = f"{remote_dir}/artifacts"
        figure_dir = f"{remote_dir}/figures"
        log_path = f"{remote_dir}/run.log"
        _run_scheduler(
            profile.mode,
            profile.host_alias,
            ["mkdir", "-p", execution_dir, output_dir, figure_dir],
        )
        entrypoint = _resolved_entrypoint(iteration, original, metadata)
        if entrypoint is None:
            raise ValueError(
                "Slurm SSH submit requires an experiment entrypoint contained in the iteration"
            )
        sources = [iteration / "config.yaml", entrypoint]
        if protocol.exists():
            sources.append(protocol)
        for source in sources:
            ensure_no_symlink(root, source)
        subprocess.run(
            [
                "scp",
                "-q",
                *[str(path) for path in sources],
                f"{profile.host_alias}:{execution_dir}/",
            ],
            check=True,
            timeout=60,
        )
    script = "\n".join(
        (
            "#!/bin/sh",
            "set -eu",
            f"export SMAIRT_PROJECT_ROOT={shlex.quote(execution_root)}",
            f"export SMAIRT_EXPERIMENT_ID={shlex.quote(experiment_id)}",
            f"export SMAIRT_ITERATION_ID={shlex.quote(iteration_id)}",
            f"export SMAIRT_RUN_ID={shlex.quote(run_id)}",
            f"export SMAIRT_CONFIG_PATH={shlex.quote(execution_dir + '/config.yaml')}",
            f"export SMAIRT_RESULTS_DIR={shlex.quote(output_dir)}",
            f"export SMAIRT_FIGURES_DIR={shlex.quote(figure_dir)}",
            f"cd {shlex.quote(execution_dir)}",
            f"exec {shlex.join(original)}",
            "",
        )
    )
    script_path = run_dir / "job.sh"
    with ProjectMutationLock(root, f"slurm submit {experiment_id}/{iteration_id}"):
        artifacts.mkdir(parents=True)
        figures.mkdir()
        atomic_write(script_path, script, mode=0o700)
        started = RunRecord(
            run_id=run_id,
            experiment_id=experiment_id,
            iteration_id=iteration_id,
            status=RunStatus.STARTED,
            command=recorded,
            started_at=utc_now(),
            working_directory=str(iteration.relative_to(root)),
            log_path=str((run_dir / "run.log").relative_to(root)),
            results_directory=str(run_dir.relative_to(root)),
            config_sha256=sha256_file(iteration / "config.yaml"),
            protocol_sha256=sha256_file(protocol) if protocol.exists() else None,
            environment={"backend": "slurm", "profile": profile_name},
            manifest_path=str((run_dir / "manifest.json").relative_to(root)),
        )
        write_json(run_dir / "run.json", started.model_dump(mode="json", exclude_none=True))
        if protocol.exists():
            safe, receipt = _safe_snapshot(protocol.read_bytes(), "protocol.snapshot.yaml")
            if receipt:
                write_json(run_dir / "provenance-omissions.json", {"omissions": [receipt]})
            elif safe is not None:
                atomic_write_bytes(run_dir / "protocol.snapshot.yaml", safe)
    try:
        submit_script = str(script_path)
        if profile.mode is ComputeMode.SSH:
            subprocess.run(
                ["scp", "-q", str(script_path), f"{profile.host_alias}:{remote_dir}/job.sh"],
                check=True,
                timeout=60,
            )
            submit_script = f"{remote_dir}/job.sh"
        output = _run_scheduler(
            profile.mode,
            profile.host_alias,
            [
                "sbatch",
                "--parsable",
                *_scheduler_args(resources),
                "--output",
                log_path,
                submit_script,
            ],
        )
    except (OSError, RuntimeError, subprocess.SubprocessError):
        failed = started.model_copy(
            update={
                "status": RunStatus.FAILED,
                "completed_at": utc_now(),
                "exit_code": 127,
                "environment": {**started.environment, "launch_failed": True},
            }
        )
        with ProjectMutationLock(root, f"slurm launch failure {run_id}"):
            atomic_write(
                run_dir / "run.log",
                "SMAIRT could not submit this Slurm run; no scheduler job was recorded.\n",
            )
            write_json(run_dir / "run.json", failed.model_dump(mode="json", exclude_none=True))
            build_manifest(root, run_dir)
        raise
    job_id = output.split(";", 1)[0].strip()
    if not re.fullmatch(r"[0-9]+(?:_[0-9]+)?", job_id):
        failed = started.model_copy(
            update={
                "status": RunStatus.FAILED,
                "completed_at": utc_now(),
                "exit_code": 127,
                "environment": {
                    **started.environment,
                    "launch_failed": True,
                    "invalid_scheduler_job_id": True,
                },
            }
        )
        with ProjectMutationLock(root, f"slurm invalid job id {run_id}"):
            atomic_write(
                run_dir / "run.log",
                "SMAIRT submitted a Slurm job but could not parse a valid job identifier.\n"
                f"Raw scheduler output: {output!r}\n",
            )
            write_json(run_dir / "run.json", failed.model_dump(mode="json", exclude_none=True))
            build_manifest(root, run_dir)
        raise RuntimeError("Slurm returned an invalid job identifier")
    job = ComputeJobRecord(
        run_id=run_id,
        experiment_id=experiment_id,
        iteration_id=iteration_id,
        mode=profile.mode,
        scheduler_job_id=job_id,
        status=ComputeJobStatus.SUBMITTED,
        submitted_at=utc_now(),
        updated_at=utc_now(),
        host_alias=profile.host_alias,
        remote_directory=remote_dir if profile.mode is ComputeMode.SSH else None,
        resources=resources,
        command=recorded,
        local_run_directory=str(run_dir.relative_to(root)),
    )
    with ProjectMutationLock(root, f"slurm receipt {run_id}"):
        write_json(run_dir / "job.json", job.model_dump(mode="json", exclude_none=True))
    return job


def load_job(root: Path, run_id: str) -> tuple[Path, ComputeJobRecord]:
    """Resolve one scheduler receipt by its SMAIRT run ID."""
    matches = list((root / "results").glob(f"*/*/{run_id}/job.json"))
    if len(matches) != 1:
        raise FileNotFoundError(f"Slurm job for {run_id} not found")
    return matches[0], ComputeJobRecord.model_validate_json(matches[0].read_text())


def refresh_job(root: Path, run_id: str) -> ComputeJobRecord:
    """Refresh scheduler state without downloading or accepting results."""
    path, job = load_job(root, run_id)
    _, profile = selected_slurm_profile()
    state = _run_scheduler(
        profile.mode,
        profile.host_alias,
        ["squeue", "-h", "-j", job.scheduler_job_id, "-o", "%T"],
    ).splitlines()
    raw = state[0].strip().upper() if state else ""
    if not raw:
        accounting = _run_scheduler(
            profile.mode,
            profile.host_alias,
            ["sacct", "-n", "-X", "-j", job.scheduler_job_id, "-o", "State", "--parsable2"],
        ).splitlines()
        raw = accounting[0].split("|", 1)[0].strip().upper() if accounting else "UNKNOWN"
    mapping = {
        "PENDING": ComputeJobStatus.PENDING,
        "CONFIGURING": ComputeJobStatus.PENDING,
        "RUNNING": ComputeJobStatus.RUNNING,
        "COMPLETED": ComputeJobStatus.COMPLETED,
        "CANCELLED": ComputeJobStatus.CANCELLED,
        "FAILED": ComputeJobStatus.FAILED,
        "TIMEOUT": ComputeJobStatus.FAILED,
        "OUT_OF_MEMORY": ComputeJobStatus.FAILED,
    }
    status = mapping.get(raw.split("+", 1)[0], ComputeJobStatus.UNKNOWN)
    job = job.model_copy(update={"status": status, "updated_at": utc_now()})
    run_dir = path.parent
    with ProjectMutationLock(root, f"slurm refresh {run_id}"):
        write_json(path, job.model_dump(mode="json", exclude_none=True))
        # Rebuild the integrity manifest whenever a hashed receipt changes.
        if (run_dir / "manifest.json").exists():
            build_manifest(root, run_dir)
    return job


def sync_job(root: Path, run_id: str) -> tuple[ComputeJobRecord, RunRecord | None]:
    """Reconcile a terminal job and atomically lock its local run bundle."""
    path, old = load_job(root, run_id)
    job = refresh_job(root, run_id)
    if job.status not in {
        ComputeJobStatus.COMPLETED,
        ComputeJobStatus.FAILED,
        ComputeJobStatus.CANCELLED,
    }:
        return job, None
    run_dir = path.parent
    if job.mode is ComputeMode.SSH and old.remote_directory:
        temporary = run_dir / ".remote-sync"
        if temporary.exists():
            shutil.rmtree(temporary)
        temporary.mkdir()
        subprocess.run(
            [
                "scp",
                "-q",
                "-r",
                f"{old.host_alias}:{old.remote_directory}/artifacts",
                str(temporary),
            ],
            check=True,
            timeout=120,
        )
        subprocess.run(
            [
                "scp",
                "-q",
                f"{old.host_alias}:{old.remote_directory}/run.log",
                str(temporary / "run.log"),
            ],
            check=True,
            timeout=60,
        )
        if (temporary / "artifacts").exists():
            current = run_dir / "artifacts"
            previous = run_dir / ".artifacts-before-sync"
            if previous.exists():
                shutil.rmtree(previous)
            if current.exists():
                current.replace(previous)
            try:
                (temporary / "artifacts").replace(current)
            except OSError:
                if previous.exists():
                    previous.replace(current)
                raise
            if previous.exists():
                shutil.rmtree(previous)
        (temporary / "run.log").replace(run_dir / "run.log")
        temporary.rmdir()
    git = _git_capture(root)
    run_status = (
        RunStatus.COMPLETED
        if job.status is ComputeJobStatus.COMPLETED
        else RunStatus.INTERRUPTED
        if job.status is ComputeJobStatus.CANCELLED
        else RunStatus.FAILED
    )
    record = RunRecord.model_validate_json((run_dir / "run.json").read_text())
    record = record.model_copy(
        update={
            "status": run_status,
            "completed_at": utc_now(),
            "exit_code": 0 if run_status is RunStatus.COMPLETED else 1,
            "git_commit": git["commit"],
            "git_dirty": bool(git["dirty"]),
            "environment": {**record.environment, "scheduler_job_id": job.scheduler_job_id},
        }
    )
    with ProjectMutationLock(root, f"slurm sync {run_id}"):
        write_json(run_dir / "run.json", record.model_dump(mode="json", exclude_none=True))
        build_manifest(root, run_dir)
    return job, record


def cancel_job(root: Path, run_id: str) -> ComputeJobRecord:
    """Cancel one explicit scheduler job and retain the receipt."""
    _, job = load_job(root, run_id)
    _, profile = selected_slurm_profile()
    _run_scheduler(profile.mode, profile.host_alias, ["scancel", job.scheduler_job_id])
    return refresh_job(root, run_id)
