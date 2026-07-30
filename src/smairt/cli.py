"""Public SMAIRT command-line interface."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Annotated, Any, cast

import typer
import yaml
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Confirm

from smairt import __version__
from smairt.cli_harness import harness_app
from smairt.cli_hpc import hpc_app, setup_hpc_app
from smairt.cli_integrations import (
    credential_app,
    integration_app,
    setup_connection_app,
    setup_openalex_app,
    setup_semantic_scholar_app,
    setup_unpaywall_app,
    setup_zotero_app,
)
from smairt.cli_literature import literature_app
from smairt.cli_mcp import mcp_app
from smairt.cli_publication import paper_app, summary_app
from smairt.cli_references import reference_app
from smairt.cli_research import (
    background_app,
    decision_app,
    experiment_app,
    hypothesis_app,
    iteration_app,
    register_root_commands,
)
from smairt.cli_safety import safety_app
from smairt.cli_shared import json_envelope
from smairt.cli_state import lock_app, recovery_app
from smairt.code_quality import build_code_index, validate_code
from smairt.contracts import check_contracts, export_contracts
from smairt.diagnostics import doctor, setup_doctor
from smairt.errors import SmairtError
from smairt.guidance import next_guidance, render_suggested_prompt
from smairt.integrity import verify_run
from smairt.migrations import apply_migration, migration_plan, rollback_migration
from smairt.model_policy import recommend_model
from smairt.models import (
    DataClassification,
    EnvironmentMode,
    HarnessName,
    ProjectLicense,
    SmairtConfig,
)
from smairt.project import context as build_context
from smairt.project import find_project, save_context_capsule, validate_project
from smairt.project import status as project_status
from smairt.provenance import add_contributor, generate_history, load_events, use_contributor
from smairt.scaffold import conda_environments, create_project
from smairt.settings import select_environment, update_project_settings
from smairt.tui import (
    SMAIRT_LOGO,
    _appearance_values,
    run_new_project,
    run_project_menu,
    run_setup_menu,
)
from smairt.updates import apply_project_updates, project_update_plan
from smairt.upgrade import upgrade_project
from smairt.utils import slugify

console = Console()


class ProjectUsageError(typer.BadParameter):
    """Represent a stable usage or project-state failure."""

    exit_code = 2

    def __init__(self, message: str, exit_code: int = 2) -> None:
        super().__init__(message)
        self.exit_code = exit_code


class FriendlyGroup(typer.core.TyperGroup):
    """Render expected domain failures without exposing implementation tracebacks."""

    def invoke(self, ctx: Any) -> object:
        """Convert domain exceptions into stable usage-or-project errors."""
        try:
            return super().invoke(ctx)
        except SmairtError as exc:
            if ctx.find_root().params.get("verbose"):
                raise
            raise ProjectUsageError(str(exc), exc.exit_code) from None
        except typer.Exit:
            raise
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            if ctx.find_root().params.get("verbose"):
                raise
            raise ProjectUsageError(str(exc)) from None


app = typer.Typer(
    help="Scientific Method with AI Research Toolkit",
    no_args_is_help=False,
    invoke_without_command=True,
    cls=FriendlyGroup,
)
start_app = typer.Typer(help="Friendly project-start aliases")
env_app = typer.Typer(help="Inspect and enter the project environment")
code_app = typer.Typer(help="Index and validate readable research code")
contributor_app = typer.Typer(help="Manage confirmed project contributors")
contract_app = typer.Typer(help="Export and check portable harness contracts")
migrate_app = typer.Typer(help="Plan, apply, and roll back schema migrations")
model_app = typer.Typer(help="Recommend economical model capability tiers")
settings_app = typer.Typer(help="Inspect and update researcher-facing project settings")
setup_app = typer.Typer(
    help="Configure and diagnose the user-wide SMAIRT tool setup",
    invoke_without_command=True,
    no_args_is_help=False,
)

app.add_typer(start_app, name="start")
app.add_typer(reference_app, name="reference")
app.add_typer(literature_app, name="literature")
app.add_typer(background_app, name="background")
app.add_typer(hypothesis_app, name="hypothesis")
app.add_typer(experiment_app, name="experiment")
app.add_typer(iteration_app, name="iteration")
app.add_typer(decision_app, name="decision")
app.add_typer(paper_app, name="paper")
app.add_typer(env_app, name="env")
app.add_typer(code_app, name="code")
app.add_typer(contributor_app, name="contributor")
app.add_typer(safety_app, name="safety")
app.add_typer(contract_app, name="contract")
app.add_typer(harness_app, name="harness")
app.add_typer(migrate_app, name="migrate")
app.add_typer(summary_app, name="summary")
app.add_typer(model_app, name="model")
app.add_typer(lock_app, name="lock")
app.add_typer(recovery_app, name="recovery")
app.add_typer(settings_app, name="settings")
app.add_typer(setup_app, name="setup")
app.add_typer(credential_app, name="credential")
app.add_typer(integration_app, name="integration")
app.add_typer(mcp_app, name="mcp")
app.add_typer(hpc_app, name="hpc")
setup_app.add_typer(credential_app, name="credential")
setup_app.add_typer(setup_connection_app, name="connection")
setup_app.add_typer(setup_zotero_app, name="zotero")
setup_app.add_typer(setup_openalex_app, name="openalex")
setup_app.add_typer(setup_semantic_scholar_app, name="semantic-scholar")
setup_app.add_typer(setup_unpaywall_app, name="unpaywall")
setup_app.add_typer(setup_hpc_app, name="hpc")
register_root_commands(app)


@contributor_app.command("add")
def contributor_add(
    name: Annotated[str, typer.Option()], email: Annotated[str | None, typer.Option()] = None
) -> None:
    """Register a contributor from explicitly supplied identity fields."""
    _emit(add_contributor(_root(), name, email).model_dump(mode="json", exclude_none=True), False)


@contributor_app.command("list")
def contributor_list(as_json: Annotated[bool, typer.Option("--json")] = False) -> None:
    """List contributors and identify the active contributor."""
    config = SmairtConfig.load(_root() / "smairt.yaml")
    _emit(
        {
            "active": config.active_contributor,
            "contributors": [
                c.model_dump(mode="json", exclude_none=True) for c in config.contributors
            ],
        },
        as_json,
    )


@contributor_app.command("use")
def contributor_use(identifier: Annotated[str, typer.Argument()]) -> None:
    """Select the contributor attributed to subsequent project actions."""
    _emit(use_contributor(_root(), identifier).model_dump(mode="json", exclude_none=True), False)


@contributor_app.command("confirm-git")
def contributor_confirm_git(yes: Annotated[bool, typer.Option("--yes")] = False) -> None:
    """Suggest Git identity but store it only after explicit confirmation."""
    root = _root()
    name = subprocess.run(
        ["git", "config", "user.name"], cwd=root, capture_output=True, text=True
    ).stdout.strip()
    email = subprocess.run(
        ["git", "config", "user.email"], cwd=root, capture_output=True, text=True
    ).stdout.strip()
    if not name:
        raise typer.BadParameter("Git user.name is not configured")
    if not yes and not Confirm.ask(f"Register Git identity {name} <{email}>?", default=False):
        raise typer.Exit()
    contributor = add_contributor(root, name, email or None, source="confirmed_git")
    use_contributor(root, contributor.id)
    _emit(contributor.model_dump(mode="json", exclude_none=True), False)


@app.command("history")
def history_command(as_json: Annotated[bool, typer.Option("--json")] = False) -> None:
    """Regenerate and display the human-readable project history."""
    root = _root()
    generate_history(root)
    _emit(load_events(root), as_json)


@app.command("doctor")
def doctor_command(as_json: Annotated[bool, typer.Option("--json")] = False) -> None:
    """Diagnose project and release health without network access or mutation."""
    payload = doctor(_root())
    if as_json:
        _emit(payload, True)
    else:
        console.print("[green]PASS[/]" if payload["ok"] else "[red]NEEDS ATTENTION[/]")
        package = cast(dict[str, object], payload["package"])
        validation = cast(dict[str, object], payload["validation"])
        git = cast(dict[str, object], payload["git"])
        environment = cast(dict[str, object], payload["environment"])
        transactions = cast(dict[str, object], payload["transactions"])
        categories = {
            "Package": not package["missing_dependencies"],
            "Project": validation["ok"],
            "Git": git["healthy"],
            "Environment": environment["healthy"],
            "Transactions": transactions["ok"],
            "Release": payload["release_ready"],
        }
        for label, ready in categories.items():
            console.print(f"{'[green]✓[/]' if ready else '[yellow]![/]'} {label}")
        findings = cast(list[dict[str, str]], validation.get("findings", []))
        for finding in findings:
            console.print(
                f"\n[bold]{finding.get('title', finding['code'])}[/]\n"
                f"{finding['message']}\n[cyan]Next:[/] "
                f"{finding.get('remediation', 'Inspect the artifact.')}"
            )
        for warning in cast(list[str], payload.get("warnings", [])):
            console.print(f"\n[yellow]Warning:[/] {escape(warning)}")
        console.print("\n[dim]Technical report: smairt doctor --json[/dim]")
    if not payload["ok"]:
        raise typer.Exit(1)


@setup_app.command("doctor")
def setup_doctor_command(
    check_github: Annotated[bool, typer.Option("--check-github")] = False,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Check tool installation and optional GitHub authentication without a project."""
    payload = setup_doctor(check_github=check_github)
    _emit(payload, as_json)
    if not payload["ok"]:
        raise typer.Exit(1)


@setup_app.callback()
def setup_main(ctx: typer.Context) -> None:
    """Open user-wide setup when no setup subcommand was supplied."""
    if ctx.invoked_subcommand is None:
        try:
            run_setup_menu()
        except KeyboardInterrupt:
            console.print("[yellow]SMAIRT setup interrupted.[/yellow]")
            raise typer.Exit(130) from None


@app.command("verify")
def verify_command(
    run: Annotated[str | None, typer.Option()] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Verify immutable hashes for one run or all recorded runs."""
    payload = verify_run(_root(), run)
    _emit(payload, as_json)
    if not payload["ok"]:
        raise typer.Exit(1)


@contract_app.command("export")
def contract_export(destination: Annotated[Path | None, typer.Option()] = None) -> None:
    """Export portable harness contract fixtures."""
    root = _root()
    _emit(export_contracts(destination or root / ".smairt/contracts/v1"), False)


@contract_app.command("check")
def contract_check(destination: Annotated[Path | None, typer.Option()] = None) -> None:
    """Validate portable harness contract fixtures."""
    root = _root()
    payload = check_contracts(destination or root / ".smairt/contracts/v1")
    _emit(payload, False)
    if not payload["ok"]:
        raise typer.Exit(1)


@migrate_app.command("plan")
def migrate_plan_command(as_json: Annotated[bool, typer.Option("--json")] = False) -> None:
    """Show the applicable migration and its preconditions."""
    _emit(migration_plan(_root()), as_json)


@migrate_app.command("apply")
def migrate_apply(
    contributor: Annotated[str | None, typer.Option()] = None,
    allow_dirty: Annotated[bool, typer.Option("--allow-dirty")] = False,
) -> None:
    """Apply the supported migration through a validated staged replacement."""
    _emit(apply_migration(_root(), contributor, allow_dirty=allow_dirty), False)


@migrate_app.command("rollback")
def migrate_rollback(yes: Annotated[bool, typer.Option("--yes")] = False) -> None:
    """Restore the latest unchanged applied migration backup."""
    if not yes and not Confirm.ask("Roll back the last migration?", default=False):
        raise typer.Exit()
    _emit(rollback_migration(_root()), False)


def _root() -> Path:
    """Resolve the current project or terminate a command with a clear error."""
    try:
        return find_project()
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(2) from exc


def _emit(payload: object, as_json: bool) -> None:
    """Render payloads either as stable JSON or readable Rich output."""
    if as_json:
        console.print_json(json.dumps(json_envelope(payload), default=str))
    else:
        console.print(payload)


def _show_guidance(root: Path) -> None:
    """Print the compact completed/recommended/alternatives handoff footer."""
    guidance = next_guidance(root)
    console.print(f"\n[bold #f28c28]Completed:[/] {guidance['completed']}")
    recommended = guidance.get("recommended")
    if recommended:
        console.print(f"[bold]Recommended next:[/] {recommended['label']}")
        reads = recommended.get("read") or []
        if reads:
            console.print("[bold]Read first:[/] " + " · ".join(str(item) for item in reads))
        if recommended.get("command"):
            console.print(f"[bold]Command:[/] [cyan]{recommended['command']}[/cyan]")
        console.print(
            Panel(
                render_suggested_prompt(root, guidance),
                title="Suggested Prompt",
                border_style="#f28c28",
            )
        )
        console.print("[dim]Copy again with: smairt next --prompt[/dim]")
    alternatives = [item["label"] for item in guidance["actions"] if item is not recommended]
    if alternatives:
        console.print("[dim]Other options: " + " · ".join(alternatives) + "[/dim]")


@app.callback()
def main(
    ctx: typer.Context,
    version: Annotated[bool, typer.Option("--version", help="Show the installed version.")] = False,
    verbose: Annotated[
        bool, typer.Option("--verbose", help="Show diagnostic exception causes.")
    ] = False,
) -> None:
    """Handle global output policy and show the deterministic SMAIRT splash."""
    del verbose
    if version:
        console.print(__version__)
        ctx.exit(0)
    if ctx.invoked_subcommand is None:
        _show_splash()


def _show_splash() -> None:
    """Show package identity and useful entry points without opening a menu."""
    try:
        root = find_project()
    except FileNotFoundError:
        root = None
    primary, secondary, mark = _appearance_values()
    body = (
        f"[bold {primary}]{SMAIRT_LOGO}[/]\n"
        + (f"[bold {secondary}]{escape(mark)}[/]\n" if mark else "")
        + f"[bold {primary}]SMAIRT {escape(__version__)}[/]\n"
        "A scientific method framework for researchers using AI\n\n"
        "Original framework: PNNL Computational Biology Group and contributors · MIT License\n"
        "Distribution: Python package [bold]smairt[/] · "
        "github.com/sarodarte2/smairt-toolkit"
    )
    console.print(Panel.fit(body, border_style=primary, padding=(1, 2)))
    if root is None:
        console.print(
            "[bold]Start here:[/] smairt new\n"
            "[dim]Also: smairt setup · smairt --help · smairt --version[/dim]"
        )
    else:
        console.print(
            f"[bold]Project detected:[/] {escape(str(root))}\n"
            "[bold]Continue:[/] smairt menu\n"
            "[dim]Also: smairt next · smairt status · smairt --help[/dim]"
        )


def _new_project(
    destination: Path | None,
    name: str | None,
    author: str | None,
    question: str | None,
    description: str | None,
    fields_of_study: list[str] | None,
    license_name: ProjectLicense,
    classification: DataClassification,
    git: bool,
    environment_mode: EnvironmentMode,
    environment_name: str | None,
    harness: HarnessName = HarnessName.CODEX,
    safety_mode: str = "standard",
    confirm_contributor: bool = False,
    allow_existing: bool = False,
) -> None:
    """Share interactive and non-interactive creation behavior across aliases."""
    if not name or not author:
        try:
            created = run_new_project(destination, allow_existing=allow_existing)
        except KeyboardInterrupt:
            console.print(
                "[yellow]Project creation interrupted; retained input was not written.[/yellow]"
            )
            raise typer.Exit(130) from None
        if created:
            console.print(f"[bold #f28c28]Created SMAIRT project:[/] {created}")
        return
    destination = (destination or Path(slugify(name))).resolve()
    config = create_project(
        destination,
        name=name,
        author=author,
        question=question,
        description=description,
        fields_of_study=fields_of_study,
        license_name=license_name,
        classification=classification,
        initialize_git=git,
        environment_mode=environment_mode,
        environment_name=environment_name,
        harness=harness,
        safety_mode=safety_mode,
        confirm_contributor=confirm_contributor,
        create_environment=environment_mode is EnvironmentMode.NEW_CONDA,
        allow_existing=allow_existing,
    )
    console.print(f"[bold #f28c28]Created {escape(config.project.name)}[/] at {destination}")
    _show_guidance(destination)


@app.command("new")
def new_command(
    destination: Annotated[Path | None, typer.Argument()] = None,
    name: Annotated[str | None, typer.Option()] = None,
    author: Annotated[str | None, typer.Option()] = None,
    question: Annotated[str | None, typer.Option()] = None,
    description: Annotated[str | None, typer.Option()] = None,
    field: Annotated[list[str] | None, typer.Option("--field")] = None,
    license_name: Annotated[ProjectLicense, typer.Option("--license")] = ProjectLicense.MIT,
    classification: Annotated[DataClassification, typer.Option()] = DataClassification.UNPUBLISHED,
    git: Annotated[bool, typer.Option("--git/--no-git")] = True,
    environment: Annotated[EnvironmentMode, typer.Option()] = EnvironmentMode.NONE,
    environment_name: Annotated[str | None, typer.Option()] = None,
    harness: Annotated[HarnessName, typer.Option()] = HarnessName.CODEX,
    safety_mode: Annotated[str, typer.Option()] = "standard",
    confirm_contributor: Annotated[bool, typer.Option("--confirm-contributor")] = False,
) -> None:
    """Create a new project; opens terminal prompts when name or author is omitted."""
    _new_project(
        destination,
        name,
        author,
        question,
        description,
        field,
        license_name,
        classification,
        git,
        environment,
        environment_name,
        harness,
        safety_mode,
        confirm_contributor,
        False,
    )


@start_app.command("project")
def start_project(
    destination: Annotated[Path | None, typer.Argument()] = None,
) -> None:
    """Deprecated alias for the interactive project wizard."""
    console.print("[yellow]smairt start project is deprecated; use smairt new.[/yellow]")
    _new_project(
        destination,
        None,
        None,
        None,
        None,
        None,
        ProjectLicense.MIT,
        DataClassification.UNPUBLISHED,
        True,
        EnvironmentMode.NONE,
        None,
        HarnessName.CODEX,
        "standard",
        False,
        False,
    )


@app.command("init")
def init_command(
    destination: Annotated[Path | None, typer.Argument()] = None,
    name: Annotated[str | None, typer.Option()] = None,
    author: Annotated[str | None, typer.Option()] = None,
) -> None:
    """Deprecated alias for initializing an existing directory."""
    console.print(
        "[yellow]smairt init is deprecated; use smairt new and choose this folder.[/yellow]"
    )
    _new_project(
        destination or Path.cwd(),
        name,
        author,
        None,
        None,
        None,
        ProjectLicense.MIT,
        DataClassification.UNPUBLISHED,
        True,
        EnvironmentMode.NONE,
        None,
        HarnessName.CODEX,
        "standard",
        False,
        True,
    )


@app.command("menu")
def menu_command(
    project: Annotated[
        Path | None, typer.Argument(help="Project folder or a folder inside it")
    ] = None,
) -> None:
    """Open the nearest dashboard, or open an existing project by path."""
    try:
        root = find_project(project.expanduser() if project is not None else None)
    except FileNotFoundError:
        requested = (project or Path.cwd()).expanduser().resolve()
        console.print(
            f"[yellow]No SMAIRT project contains {escape(str(requested))}.[/yellow]\n"
            "Create one with [bold]smairt new[/bold], or open an existing one with\n"
            "[bold]smairt menu /path/to/project[/bold]."
        )
        raise typer.Exit(2) from None
    try:
        run_project_menu(root)
    except KeyboardInterrupt:
        console.print("[yellow]SMAIRT interrupted.[/yellow]")
        raise typer.Exit(130) from None


@settings_app.command("show")
def settings_show(as_json: Annotated[bool, typer.Option("--json")] = False) -> None:
    """Show the durable researcher-facing project settings."""
    config = SmairtConfig.load(_root() / "smairt.yaml")
    _emit(
        {
            "schema_version": config.schema_version,
            "project": config.project.model_dump(mode="json", exclude_none=True),
            "environment": config.environment.model_dump(mode="json", exclude_none=True),
            "integrations": config.integrations.model_dump(mode="json", exclude_none=True),
            "active_contributor": config.active_contributor,
        },
        as_json,
    )


@settings_app.command("project")
def settings_project(
    name: Annotated[str | None, typer.Option()] = None,
    author: Annotated[str | None, typer.Option()] = None,
    question: Annotated[str | None, typer.Option()] = None,
    description: Annotated[str | None, typer.Option()] = None,
    field: Annotated[list[str] | None, typer.Option("--field")] = None,
    license_name: Annotated[ProjectLicense | None, typer.Option("--license")] = None,
) -> None:
    """Update project identity, fields of study, and the managed license."""
    root = _root()
    config = SmairtConfig.load(root / "smairt.yaml")
    updated = update_project_settings(
        root,
        name=name if name is not None else config.project.name,
        author=author if author is not None else config.project.author,
        question=question if question is not None else config.project.question,
        description=description if description is not None else config.project.description,
        fields_of_study=field if field is not None else config.project.fields_of_study,
        license_name=license_name if license_name is not None else config.project.license,
    )
    _emit(updated.project.model_dump(mode="json", exclude_none=True), False)


@app.command("upgrade")
def upgrade_command(
    apply: Annotated[bool, typer.Option("--apply")] = False,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Preview or apply safe framework-managed guidance updates."""
    root = _root()
    payload = upgrade_project(root, apply=apply)
    _emit(payload, as_json)
    if apply:
        _show_guidance(root)


@app.command("update")
def update_command(
    apply: Annotated[bool, typer.Option("--apply")] = False,
    yes: Annotated[bool, typer.Option("--yes")] = False,
    allow_dirty: Annotated[bool, typer.Option("--allow-dirty")] = False,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Preview or apply schema, guidance, and active-adapter updates together."""
    root = _root()
    if (
        apply
        and not yes
        and not Confirm.ask("Apply every conflict-free project update?", default=False)
    ):
        raise typer.Exit()
    payload = (
        apply_project_updates(
            root,
            contributor_id=SmairtConfig.load(root / "smairt.yaml").active_contributor,
            allow_dirty=allow_dirty,
        )
        if apply
        else project_update_plan(root)
    )
    _emit(payload, as_json)


@app.command("status")
def status_command(
    as_json: Annotated[bool, typer.Option("--json")] = False,
    compact: Annotated[bool, typer.Option("--compact")] = False,
) -> None:
    """Show project identity, active artifacts, health, and optionally full JSON."""
    payload = project_status(_root())
    if as_json:
        _emit(payload, True)
        return
    project = cast(dict[str, Any], payload["project"])
    console.print(
        f"[bold #f28c28]{escape(str(project['name']))}[/] · "
        f"{escape(str(payload['data_classification']))}"
    )
    console.print(f"Author: {escape(str(project['author']))}")
    console.print(f"Active: {payload['active'] or 'none'}")
    console.print(f"Stage: {escape(str(payload.get('stage', 'unknown')))}")
    validation = cast(dict[str, Any], payload["validation"])
    console.print(f"Validation: {'PASS' if validation['ok'] else 'FAIL'}")
    if not compact:
        console.print(payload["counts"])
        readiness = cast(dict[str, Any], payload.get("readiness", {}))
        if readiness:
            ready = ", ".join(
                f"{key}={'yes' if value else 'no'}" for key, value in readiness.items()
            )
            console.print(f"Readiness: {ready}")
        guidance = cast(dict[str, Any], payload.get("guidance", {}))
        recommended = next(
            (
                action
                for action in cast(list[dict[str, Any]], guidance.get("actions", []))
                if action.get("recommended")
            ),
            None,
        )
        if recommended:
            console.print(f"Next: {escape(str(recommended.get('label', '')))}")
            if recommended.get("command"):
                console.print(f"  [cyan]{escape(str(recommended['command']))}[/]")
        for warning in validation["warnings"]:
            console.print(f"[yellow]Warning:[/] {escape(str(warning))}")


@app.command("validate")
def validate_command(
    as_json: Annotated[bool, typer.Option("--json")] = False,
    staged: Annotated[bool, typer.Option("--staged")] = False,
    tool_input: Annotated[bool, typer.Option("--tool-input", hidden=True)] = False,
) -> None:
    """Run structural, safety, code, provenance, and readiness validation."""
    report = validate_project(_root(), staged=staged, tool_input=tool_input)
    if as_json:
        _emit(report.as_dict(), True)
    else:
        console.print("[green]PASS[/]" if report.ok else "[red]FAIL[/]")
        for error in report.errors:
            console.print(f"[red]Error:[/] {error}")
        for warning in report.warnings:
            console.print(f"[yellow]Warning:[/] {warning}")
    if not report.ok:
        raise typer.Exit(1)


@app.command("context")
def context_command(
    task: Annotated[
        str, typer.Option(help="planning, code, run, interpretation, paper, or review")
    ],
    token_budget: Annotated[int, typer.Option("--token-budget", min=1)] = 8000,
    target: Annotated[
        str | None,
        typer.Option(help="Project-relative textual artifact; valid only for review context"),
    ] = None,
    save: Annotated[bool, typer.Option("--save")] = False,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Return only the initial files relevant to the requested research task."""
    payload = build_context(_root(), task, token_budget, target)
    if save:
        payload["capsule_path"] = str(save_context_capsule(_root(), payload).relative_to(_root()))
    _emit(payload, as_json)


@model_app.command("recommend")
def model_recommend(
    task: Annotated[str, typer.Option()],
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Recommend a provider-neutral model tier for a research task."""
    _emit(recommend_model(_root(), task), as_json)


@app.command("next")
def next_command(
    as_json: Annotated[bool, typer.Option("--json")] = False,
    prompt: Annotated[bool, typer.Option("--prompt")] = False,
) -> None:
    """Show the state-aware next actions for this research project."""
    if as_json and prompt:
        raise typer.BadParameter("--json and --prompt cannot be combined")
    root = _root()
    payload = next_guidance(root)
    suggested = render_suggested_prompt(root, payload)
    if prompt:
        console.print(suggested, markup=False)
        return
    if as_json:
        payload["suggested_prompt"] = suggested
        _emit(payload, True)
    else:
        _show_guidance(root)


@code_app.command("index")
def code_index(
    check: Annotated[bool, typer.Option("--check")] = False,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Build the AST-derived code index, or check whether it is current."""
    root = _root()
    payload = build_code_index(root, write=not check)
    if check:
        path = root / "scripts/CODE_INDEX.yaml"
        current = yaml.safe_load(path.read_text()) if path.exists() else None
        payload = {"current": current == payload, "index": payload}
        if not payload["current"]:
            _emit(payload, as_json)
            raise typer.Exit(1)
    _emit(payload, as_json)


@code_app.command("validate")
def code_validate(
    path: Annotated[Path | None, typer.Argument()] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Report human-readability and traceability findings without blocking research."""
    root = _root()
    target = (root / path).resolve() if path and not path.is_absolute() else path
    findings = validate_code(root, target)
    _emit(
        {"ok": not any(item["severity"] == "error" for item in findings), "findings": findings},
        as_json,
    )


@env_app.command("status")
def env_status(as_json: Annotated[bool, typer.Option("--json")] = False) -> None:
    """Show the configured environment and locally discoverable Conda options."""
    config = SmairtConfig.load(_root() / "smairt.yaml")
    payload = {
        "configured": config.environment.model_dump(mode="json", exclude_none=True),
        "available_conda_environments": conda_environments(),
    }
    _emit(payload, as_json)


@env_app.command("select")
def env_select(
    mode: Annotated[EnvironmentMode, typer.Option()],
    name: Annotated[str | None, typer.Option()] = None,
    prefix: Annotated[str | None, typer.Option()] = None,
    create: Annotated[bool, typer.Option("--create")] = False,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Select or create the Conda environment used for project commands."""
    selected = select_environment(_root(), mode=mode, name=name, prefix=prefix, create=create)
    _emit(selected.model_dump(mode="json", exclude_none=True), as_json)


@env_app.command("shell")
def env_shell() -> None:
    """Open a shell inside the configured environment when one is managed."""
    config = SmairtConfig.load(_root() / "smairt.yaml")
    shell = os.environ.get("SHELL", "/bin/sh")
    if config.environment.mode is EnvironmentMode.NEW_CONDA and config.environment.name:
        command = ["conda", "run", "-n", config.environment.name, shell]
    elif config.environment.mode is EnvironmentMode.EXISTING_CONDA and config.environment.prefix:
        command = ["conda", "run", "-p", config.environment.prefix, shell]
    else:
        command = [shell]
    raise typer.Exit(subprocess.run(command, check=False).returncode)
