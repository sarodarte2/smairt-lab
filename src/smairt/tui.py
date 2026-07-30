"""Terminal-native prompt workflows for project creation and maintenance."""

from __future__ import annotations

import os
import re
import time
from contextlib import suppress
from html import escape as escape_html
from pathlib import Path
from typing import Any, TypedDict, TypeVar, cast

from prompt_toolkit import Application, PromptSession
from prompt_toolkit.application.current import get_app
from prompt_toolkit.completion import FuzzyCompleter, WordCompleter
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.key_binding.key_processor import KeyPressEvent
from prompt_toolkit.layout import Dimension, DynamicContainer, HSplit, Layout, VSplit, Window
from prompt_toolkit.layout.containers import AnyContainer
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.shortcuts import CompleteStyle
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Box, Frame, RadioList
from rich.console import Console
from rich.markup import escape as escape_rich
from rich.panel import Panel
from rich.table import Table

from smairt.completion import PROJECT_ACTIONS
from smairt.credentials import delete_credential, keyring_health, set_credential
from smairt.diagnostics import doctor, setup_doctor
from smairt.guidance import next_guidance, render_suggested_prompt
from smairt.harness_presentation import HARNESS_PRESENTATIONS
from smairt.harnesses import configure_mcp, select_harness
from smairt.integrations import (
    configure_openalex,
    configure_zotero,
    integration_health,
)
from smairt.literature import (
    literature_access,
    literature_recommend,
    literature_related,
    literature_search,
)
from smairt.local_setup import (
    AppearanceConfig,
    ConnectionProfile,
    ProviderName,
    SlurmProfile,
    bind_profile,
    configure_profile,
    configure_slurm_profile,
    delete_profile,
    discover_zotero_libraries,
    iter_profiles,
    load_bindings,
    load_custom_logo,
    load_user_setup,
    provider_profiles,
    save_custom_logo,
    save_user_setup,
    test_profile,
    unbind_profile,
)
from smairt.migrations import apply_migration, migration_plan
from smairt.models import (
    ComputeMode,
    DataClassification,
    EnvironmentMode,
    HarnessName,
    LiteratureCandidate,
    ProjectLicense,
    SafetyMode,
    SmairtConfig,
    ZoteroLibraryType,
    ZoteroMode,
)
from smairt.project import find_project, status
from smairt.provenance import add_contributor, use_contributor
from smairt.references import (
    add_doi_reference,
    add_reference,
    attach_reference,
    copy_zotero_attachment,
    edit_reference,
    import_zotero_collection,
    import_zotero_item,
    inspect_pdf,
    load_index,
    verify_reference,
)
from smairt.safety import release_check, safety_status, set_safety_mode
from smairt.scaffold import conda_environments, create_project
from smairt.settings import select_environment, update_project_settings
from smairt.updates import apply_project_updates, project_update_plan
from smairt.utils import slugify
from smairt.zotero import ZoteroProvider, public_item

ORANGE = "#f28c28"
CYAN = "#62d6e8"
SMAIRT_LOGO = r"""  _____ __  __    _    ___ ____ _____
 / ___/|  \/  |  / \  |_ _|  _ \_   _|
 \___ \| |\/| | / _ \  | || |_) || |
  ___) | |  | |/ ___ \ | ||  _ < | |
 |____/|_|  |_/_/   \_\___|_| \_\|_|"""
THEMES: dict[str, tuple[str, str, str, str, str, str, str]] = {
    "scientific": (ORANGE, CYAN, "#f1f1f1", "#8b909c", "#5fd38d", "#ffd166", "#ff6b6b"),
    "pnnl": ("#d97706", "#94a3b8", "#f8fafc", "#94a3b8", "#65a30d", "#f59e0b", "#dc2626"),
    "utep": ("#ff8200", "#4f83cc", "#f8fafc", "#9ca3af", "#22c55e", "#f59e0b", "#ef4444"),
    "matrix": ("#00ff41", "#008f11", "#d7ffd9", "#67a66f", "#00ff41", "#d7ff00", "#ff5f56"),
    "dracula": ("#ff79c6", "#8be9fd", "#f8f8f2", "#6272a4", "#50fa7b", "#f1fa8c", "#ff5555"),
    "nord": ("#88c0d0", "#81a1c1", "#eceff4", "#7b88a1", "#a3be8c", "#ebcb8b", "#bf616a"),
    "solarized": ("#b58900", "#2aa198", "#eee8d5", "#839496", "#859900", "#cb4b16", "#dc322f"),
    "amber": ("#ffb000", "#ffd166", "#fff3c4", "#b89b62", "#9acd32", "#ffd166", "#ff6b35"),
    "high-contrast": ("#ffff00", "#00ffff", "#ffffff", "#c0c0c0", "#00ff00", "#ffff00", "#ff4040"),
    "monochrome": ("#ffffff", "#d0d0d0", "#ffffff", "#a3a3a3", "#ffffff", "#d0d0d0", "#ffffff"),
}
_LAUNCH_ANIMATED = False
_SCREEN_TITLE = "SMAIRT"
_SCREEN_SUBTITLE = ""
_SCREEN_CARDS: tuple[tuple[str, str], ...] = ()
_APPEARANCE_PREVIEW: AppearanceConfig | None = None
FIELD_SUGGESTIONS = (
    "Machine learning, Data science, Computational biology, Physics, Chemistry, Engineering"
)
console = Console()
T = TypeVar("T")


class WizardValues(TypedDict):
    """Retained values for every creation step."""

    destination: str
    creation_mode: str
    parent: str
    folder: str
    name: str
    author: str
    email: str
    question: str
    description: str
    fields: str
    classification: DataClassification
    license: ProjectLicense
    environment: EnvironmentMode
    environment_name: str
    harness: HarnessName
    safety_mode: SafetyMode
    git: bool
    confirm_contributor: bool
    collaborators: list[tuple[str, str | None]]


class BackNavigation(Exception):
    """Signal Escape without treating ordinary navigation as an error."""


class _WrappingRadioList(RadioList[T]):
    """Provide circular arrow navigation for Prompt Toolkit choice menus."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        bindings = cast(KeyBindings, self.control.key_bindings)

        @bindings.add("up", eager=True)
        @bindings.add("k", eager=True)
        def move_up(event: KeyPressEvent) -> None:
            del event
            action_count = len(self.values)
            self._selected_index = (self._selected_index - 1) % action_count
            self.current_value = self.values[self._selected_index][0]

        @bindings.add("down", eager=True)
        @bindings.add("j", eager=True)
        def move_down(event: KeyPressEvent) -> None:
            del event
            action_count = len(self.values)
            self._selected_index = (self._selected_index + 1) % action_count
            self.current_value = self.values[self._selected_index][0]

        @bindings.add("tab", eager=True)
        def select_back(event: KeyPressEvent) -> None:
            del event
            self._selected_index = len(self.values) - 1
            self.current_value = self.values[self._selected_index][0]


def _back_bindings() -> KeyBindings:
    """Bind Escape to a typed navigation signal for every prompt."""
    bindings = KeyBindings()

    @bindings.add("escape", eager=True)
    @bindings.add("left", eager=True)
    def go_back(event: KeyPressEvent) -> None:
        event.app.exit(exception=BackNavigation())

    @bindings.add("c-c", eager=True)
    def interrupt(event: KeyPressEvent) -> None:
        event.app.exit(exception=KeyboardInterrupt())

    return bindings


def _responsive_menu_container(message: str, chooser: RadioList[Any]) -> AnyContainer:
    """Build the current menu from the live terminal dimensions on every redraw."""
    size = get_app().output.get_size()
    width, height = size.columns, size.rows
    tier, max_width = _responsive_layout(width, height)
    appearance = _APPEARANCE_PREVIEW or load_user_setup().appearance
    _primary, _secondary, mark = _appearance_values(appearance)
    mark_label = "CUSTOM" if appearance.mark == "custom" else ""
    wide = tier == "wide"
    compact = tier == "compact"
    if wide:
        wordmark_lines = SMAIRT_LOGO.splitlines()
        mark_lines = mark.splitlines() if mark else []
        brand_lines = []
        for index in range(max(len(wordmark_lines), len(mark_lines))):
            wordmark_line = wordmark_lines[index] if index < len(wordmark_lines) else ""
            mark_line = mark_lines[index] if index < len(mark_lines) else ""
            brand_lines.append(
                f"<primary>{escape_html(wordmark_line)}</primary>"
                + (f"    <cyan>{escape_html(mark_line)}</cyan>" if mark_line else "")
            )
        identity = HTML(
            "\n".join(brand_lines) + "\n"
            "<cyan>Research workspace</cyan>  "
            f"<primary>{escape_html(_SCREEN_TITLE)}</primary>\n"
            f"<muted>{escape_html(_SCREEN_SUBTITLE)}</muted>"
        )
    elif compact:
        identity = HTML(
            "<primary>◆ SMAIRT</primary>  "
            + (f"<cyan>[{mark_label}]</cyan>  " if mark_label else "")
            + f"<cyan>{escape_html(_SCREEN_TITLE)}</cyan>\n"
            f"<muted>{escape_html(_SCREEN_SUBTITLE)}</muted>"
        )
    else:
        badge = f" [{mark_label}]" if mark_label else ""
        identity = HTML(f"<primary>◆ SMAIRT{badge} · {escape_html(_SCREEN_TITLE)}</primary>")
        if _SCREEN_SUBTITLE and height >= 16:
            identity = HTML(
                f"<primary>◆ SMAIRT{badge} · {escape_html(_SCREEN_TITLE)}</primary>\n"
                f"<muted>{escape_html(_SCREEN_SUBTITLE)}</muted>"
            )
    if wide:
        header_height = max(8, max(len(SMAIRT_LOGO.splitlines()), len(mark.splitlines())) + 2)
    else:
        header_height = 3 if compact else 2
    cards: list[AnyContainer] = []
    if _SCREEN_CARDS and height >= 18:
        card_windows = [
            Frame(
                Box(Window(FormattedTextControl(value), height=1), padding=0),
                title=label,
                style="class:card",
            )
            for label, value in _SCREEN_CARDS
        ]
        if wide:
            cards = [VSplit(card_windows, padding=1, padding_char=" ", height=3)]
        elif compact:
            midpoint = (len(card_windows) + 1) // 2
            cards = [
                VSplit(card_windows[:midpoint], padding=1, height=3),
                VSplit(card_windows[midpoint:], padding=1, height=3),
            ]
        else:
            summary = " · ".join(f"{label}: {value}" for label, value in _SCREEN_CARDS)
            cards = [Window(FormattedTextControl(summary), height=1)]
    body = HSplit(
        [
            Frame(
                Box(Window(FormattedTextControl(identity), height=header_height), padding=1),
                style="class:brand",
            ),
            *cards,
            Window(
                FormattedTextControl(HTML(f"<question>{escape_html(message)}</question>")),
                height=1,
            ),
            chooser,
            Window(
                FormattedTextControl(
                    HTML(
                        "<footer>↑↓ move · Enter select · choose Back or ←/Esc · "
                        "Ctrl-C exit</footer>"
                    )
                ),
                height=1,
            ),
        ],
        padding=1,
    )
    return VSplit(
        [
            Window(width=Dimension(weight=1)),
            Box(body, width=Dimension(preferred=max_width, max=max_width), padding=0),
            Window(width=Dimension(weight=1)),
        ]
    )


def _responsive_layout(width: int, height: int) -> tuple[str, int]:
    """Return the deterministic renderer tier and centered content-width cap."""
    if width >= 120 and height >= 28:
        return "wide", min(width, 132)
    if width >= 80 and height >= 24:
        return "compact", min(width, 132)
    return "narrow", min(width, 132)


def _appearance_values(config: AppearanceConfig | None = None) -> tuple[str, str, str]:
    """Resolve accessible accents and one optional safe secondary mark."""
    appearance = config or _APPEARANCE_PREVIEW or load_user_setup().appearance
    if os.environ.get("NO_COLOR"):
        primary, secondary, *_rest = THEMES["monochrome"]
    elif appearance.theme == "custom":
        primary = appearance.primary_color or ORANGE
        secondary = appearance.secondary_color or CYAN
    else:
        primary, secondary, *_rest = THEMES[appearance.theme]
    mark = {"none": "", "custom": load_custom_logo() or ""}[appearance.mark]
    return primary, secondary, mark


def _theme_values(config: AppearanceConfig | None = None) -> tuple[str, ...]:
    """Return semantic terminal colors while respecting custom and no-color modes."""
    appearance = config or _APPEARANCE_PREVIEW or load_user_setup().appearance
    if os.environ.get("NO_COLOR"):
        return THEMES["monochrome"]
    if appearance.theme == "custom":
        primary = appearance.primary_color or ORANGE
        secondary = appearance.secondary_color or CYAN
        return (primary, secondary, "#f1f1f1", "#8b909c", "#5fd38d", "#ffd166", "#ff6b6b")
    return THEMES[appearance.theme]


def _select(message: str, options: list[tuple[T, str]], default: T | None = None) -> T:
    """Select one responsive option with retained focus, circular movement, and Back."""
    if not options:
        raise ValueError("selection requires at least one option")
    back_token = object()
    has_back = any(value == "back" for value, _label in options)
    visible_options: list[tuple[object, str]] = list(options)
    if not has_back:
        visible_options.append((back_token, "← Back"))
    selected = default if default is not None else visible_options[0][0]
    chooser: _WrappingRadioList[Any] = _WrappingRadioList(
        visible_options,
        default=selected,
    )
    bindings = _back_bindings()

    @bindings.add("enter", eager=True)
    def accept(event: KeyPressEvent) -> None:
        value = chooser.current_value
        if value is back_token:
            event.app.exit(exception=BackNavigation())
        else:
            event.app.exit(result=value)

    primary, secondary, text, muted, success, warning, error = _theme_values()

    application: Application[Any] = Application(
        layout=Layout(DynamicContainer(lambda: _responsive_menu_container(message, chooser))),
        key_bindings=bindings,
        style=Style.from_dict(
            {
                "primary": primary,
                "orange": primary,
                "cyan": secondary,
                "muted": muted,
                "question": f"bold {text}",
                "footer": muted,
                "radio-selected": f"bold {primary}",
                "radio-checked": secondary,
                "frame.label": secondary,
                "brand": text,
                "card": text,
                "success": success,
                "warning": warning,
                "error": error,
            }
        ),
        full_screen=False,
        erase_when_done=True,
        terminal_size_polling_interval=0.25,
        min_redraw_interval=0.03,
    )
    application.ttimeoutlen = 0.05
    return cast(T, application.run())


def _text(message: str, default: str = "") -> str:
    """Read an editable inline value and preserve the supplied default."""
    session: PromptSession[str] = PromptSession()
    session.app.ttimeoutlen = 0.05
    return session.prompt(f"{message}: ", default=default, key_bindings=_back_bindings()).strip()


def _command_palette() -> str:
    """Search project actions in a local multi-column popup beneath the cursor."""
    display = {
        f"{item.value}  {item.label}": f"{item.description} · {item.effect}"
        for item in PROJECT_ACTIONS
    }
    completer = FuzzyCompleter(
        WordCompleter(
            list(display),
            meta_dict=display,
            sentence=True,
            match_middle=True,
        )
    )
    session: PromptSession[str] = PromptSession(completer=completer)
    session.app.ttimeoutlen = 0.05
    value = session.prompt(
        "Find an action: ",
        complete_while_typing=True,
        complete_style=CompleteStyle.MULTI_COLUMN,
        key_bindings=_back_bindings(),
    ).strip()
    token = value.split(maxsplit=1)[0] if value else ""
    valid = {item.value for item in PROJECT_ACTIONS}
    if token not in valid:
        raise ValueError("choose one of the suggested SMAIRT actions")
    return token


def _secret(message: str) -> str:
    """Read a masked credential without retaining it in terminal history."""
    session: PromptSession[str] = PromptSession()
    return session.prompt(f"{message}: ", is_password=True, key_bindings=_back_bindings()).strip()


def _yes_no(message: str, default: bool = True) -> bool:
    """Ask one explicit inline yes/no question."""
    return _select(
        message,
        [(True, "Yes"), (False, "No")],
        default=default,
    )


def _pause() -> None:
    """Keep a result readable before redrawing the next menu."""
    with suppress(BackNavigation):
        _text("Press Enter to continue")


def _header(title: str, subtitle: str = "") -> None:
    """Set identity for the next responsive screen and animate only once per launch."""
    global _LAUNCH_ANIMATED, _SCREEN_CARDS, _SCREEN_SUBTITLE, _SCREEN_TITLE
    _SCREEN_TITLE = title
    _SCREEN_SUBTITLE = subtitle
    _SCREEN_CARDS = ()
    width, height = console.size
    if console.is_terminal:
        console.clear(home=True)
    motion = (
        console.is_terminal
        and not _LAUNCH_ANIMATED
        and load_user_setup().appearance.motion == "automatic"
        and os.environ.get("SMAIRT_REDUCED_MOTION") != "1"
        and not os.environ.get("CI")
        and os.environ.get("TERM") != "dumb"
        and width >= 72
        and height >= 20
    )
    if motion:
        time.sleep(0.06)
        _LAUNCH_ANIMATED = True
    # Redirected output and test captures cannot run the interactive renderer;
    # retain a concise identity line for logs and accessibility tooling.
    if hasattr(console.file, "getvalue"):
        primary, secondary, mark = _appearance_values()
        if width >= 120 and height >= 28:
            console.print(
                f"[bold {primary}]{SMAIRT_LOGO}[/]"
                + (f"\n[bold {secondary}]{escape_rich(mark)}[/]" if mark else "")
                + f"\n[bold {secondary}]Scientific Method[/]\n"
                f"[bold]{title}[/] · {subtitle}"
            )
        else:
            mark_label = (
                "CUSTOM"
                if (_APPEARANCE_PREVIEW or load_user_setup().appearance).mark == "custom"
                else None
            )
            badge = f" [{mark_label}]" if mark_label else ""
            identity = f"[bold {primary}]◆ SMAIRT{badge} · {title}[/]"
            console.print(identity + (f"\n{subtitle}" if subtitle else ""))


def _cards(*values: tuple[str, object]) -> None:
    """Attach compact status cards to the next menu render."""
    global _SCREEN_CARDS
    _SCREEN_CARDS = tuple((label, str(value)) for label, value in values)


def _render_harness_chooser(active: HarnessName | None = None) -> None:
    """Show concise harness tradeoffs before asking the researcher to choose."""
    if console.width >= 96:
        table = Table(header_style=f"bold {ORANGE}", box=None, expand=True)
        table.add_column("Harness", style="bold", no_wrap=True)
        table.add_column("Best for", ratio=2)
        table.add_column("Workflow", ratio=1)
        table.add_column("Review", ratio=2)
        for name, details in HARNESS_PRESENTATIONS.items():
            marker = "◆ " if name is active else ""
            table.add_row(
                marker + details.display_name,
                details.best_for,
                details.invocation,
                details.reviewer,
            )
        console.print(table)
    else:
        for name, details in HARNESS_PRESENTATIONS.items():
            marker = "◆ " if name is active else "  "
            console.print(f"{marker}[bold]{details.display_name}[/] · {details.tagline}")
    console.print("[dim]No harness replaces SMAIRT's CLI and human scientific gates.[/dim]\n")


def _preflight_destination(destination: Path, *, allow_existing: bool) -> None:
    """Reject unsafe destinations before a creation confirmation is shown."""
    resolved = destination.expanduser().resolve()
    if (resolved / "smairt.yaml").exists():
        raise FileExistsError("destination is already a SMAIRT project; use 'smairt menu'")
    if (
        resolved.exists()
        and any(resolved.iterdir())
        and not (resolved / ".git").exists()
        and not allow_existing
    ):
        raise FileExistsError(
            "destination contains files; choose an empty folder or use 'smairt init'"
        )


def run_new_project(
    destination: Path | None = None, *, allow_existing: bool = False
) -> Path | None:
    """Run a retained-state creation workflow directly in the shell transcript."""
    values: WizardValues = {
        "destination": "",
        "creation_mode": "initialize" if allow_existing else "new",
        "parent": str(destination or Path.cwd()),
        "folder": "",
        "name": "",
        "author": "",
        "email": "",
        "question": "",
        "description": "",
        "fields": "",
        "classification": DataClassification.UNPUBLISHED,
        "license": ProjectLicense.MIT,
        "environment": EnvironmentMode.NONE,
        "environment_name": "",
        "harness": HarnessName.CODEX,
        "safety_mode": SafetyMode.STANDARD,
        "git": True,
        "confirm_contributor": True,
        "collaborators": [],
    }
    step = 0
    while True:
        try:
            if step == 0:
                _header("SMAIRT · New Project", "Choose where the project will live")
                values["creation_mode"] = _select(
                    "Creation mode",
                    [
                        ("new", "Create a new folder inside a parent directory"),
                        ("initialize", "Initialize an existing folder in place"),
                        ("cancel", "Cancel"),
                    ],
                    values["creation_mode"],
                )
                if values["creation_mode"] == "cancel":
                    return None
                step = 1
            elif step == 1:
                _header("SMAIRT · New Project", "Step 1 of 5 · Location")
                values["name"] = _text("Project name", str(values["name"]))
                if not values["name"]:
                    raise ValueError("project name is required")
                if values["creation_mode"] == "new":
                    values["parent"] = _text("Parent directory", str(values["parent"]))
                    values["folder"] = _text(
                        "Project folder", str(values["folder"] or slugify(values["name"]))
                    )
                    if not values["folder"] or Path(values["folder"]).name != values["folder"]:
                        raise ValueError("project folder must be one folder name")
                    target = Path(values["parent"]).expanduser() / values["folder"]
                    try:
                        ancestor = find_project(Path(values["parent"]).expanduser())
                    except FileNotFoundError:
                        ancestor = None
                    if ancestor is not None and not _yes_no(
                        f"Create a separate nested project under {ancestor}?", False
                    ):
                        continue
                    _preflight_destination(target, allow_existing=False)
                else:
                    existing_default = values["destination"] or str(destination or Path.cwd())
                    target = Path(_text("Existing folder", existing_default)).expanduser()
                    _preflight_destination(target, allow_existing=True)
                values["destination"] = str(target.resolve())
                step = 2
            elif step == 2:
                _header("SMAIRT · New Project", "Step 2 of 5 · Research identity")
                values["question"] = _text(
                    "Initial research question (optional)", values["question"]
                )
                values["description"] = _text(
                    "Project description (optional)", values["description"]
                )
                console.print(f"[dim]Suggestions: {FIELD_SUGGESTIONS}[/dim]")
                values["fields"] = _text(
                    "Fields of study, comma separated (optional)", str(values["fields"])
                )
                step = 3
            elif step == 3:
                _header("SMAIRT · New Project", "Step 3 of 5 · People")
                values["author"] = _text("Primary researcher", str(values["author"]))
                if not values["author"]:
                    raise ValueError("primary researcher is required")
                values["email"] = _text("Email (optional)", str(values["email"]))
                values["confirm_contributor"] = _yes_no(
                    "Register this researcher as the active contributor?",
                    bool(values["confirm_contributor"]),
                )
                collaborators = list(values["collaborators"])
                while _yes_no("Add another collaborator?", False):
                    collaborator_name = _text("Collaborator name")
                    collaborator_email = _text("Collaborator email (optional)")
                    if not collaborator_name:
                        raise ValueError("collaborator name is required")
                    identifiers = {slugify(str(item[0])) for item in collaborators}
                    identifiers.add(slugify(str(values["author"])))
                    if slugify(collaborator_name) in identifiers:
                        raise ValueError("collaborator names must be unique")
                    collaborators.append((collaborator_name, collaborator_email or None))
                values["collaborators"] = collaborators
                step = 4
            elif step == 4:
                _header("SMAIRT · New Project", "Step 4 of 5 · Policy and tools")
                values["classification"] = _select(
                    "Data classification",
                    [(item, item.value.title()) for item in DataClassification],
                    values["classification"],
                )
                values["license"] = _select(
                    "Project license",
                    [(item, item.value) for item in ProjectLicense],
                    values["license"],
                )
                values["environment"] = _select(
                    "Project environment",
                    [
                        (EnvironmentMode.NONE, "No managed environment"),
                        (EnvironmentMode.NEW_CONDA, "Create a new Conda environment"),
                    ],
                    values["environment"],
                )
                if values["environment"] is EnvironmentMode.NEW_CONDA:
                    default_name = values["environment_name"] or slugify(values["name"])
                    values["environment_name"] = _text("Conda environment name", default_name)
                _render_harness_chooser(values["harness"])
                values["harness"] = _select(
                    "Coding harness",
                    [(item, HARNESS_PRESENTATIONS[item].display_name) for item in HarnessName],
                    values["harness"],
                )
                values["safety_mode"] = _select(
                    "Safety mode",
                    [(item, item.value.title()) for item in SafetyMode],
                    values["safety_mode"],
                )
                values["git"] = _yes_no("Initialize Git?", bool(values["git"]))
                step = 5
            else:
                _header("SMAIRT · New Project", "Step 5 of 5 · Review")
                console.print(
                    f"[bold]{values['name']}[/] at "
                    f"{Path(values['destination']).expanduser()}\n"
                    f"Researcher: {values['author']} · Fields: {values['fields'] or 'not set'}\n"
                    f"Data: {values['classification'].value} · License: {values['license'].value}\n"
                    f"Environment: {values['environment'].value} · "
                    f"Harness: {values['harness'].value}\n"
                    f"Safety: {values['safety_mode'].value} · Git: {values['git']}"
                )
                action = _select(
                    "Review",
                    [
                        ("create", "Create project"),
                        ("back", "Change choices"),
                        ("cancel", "Cancel"),
                    ],
                    "create",
                )
                if action == "cancel":
                    return None
                if action == "back":
                    step = 4
                    continue
                target = Path(values["destination"]).expanduser().resolve()
                fields = [item.strip() for item in str(values["fields"]).split(",") if item.strip()]
                with console.status("[bold]Creating project…[/bold]", spinner="dots"):
                    create_project(
                        target,
                        name=values["name"],
                        author=values["author"],
                        author_email=values["email"] or None,
                        question=values["question"] or None,
                        description=values["description"] or None,
                        fields_of_study=fields,
                        license_name=values["license"],
                        classification=values["classification"],
                        initialize_git=bool(values["git"]),
                        environment_mode=values["environment"],
                        environment_name=values["environment_name"] or None,
                        create_environment=values["environment"] is EnvironmentMode.NEW_CONDA,
                        harness=values["harness"],
                        safety_mode=values["safety_mode"].value,
                        confirm_contributor=bool(values["confirm_contributor"]),
                        allow_existing=values["creation_mode"] == "initialize",
                    )
                for saved_name, saved_email in values["collaborators"]:
                    add_contributor(target, saved_name, saved_email)
                _header("Project created", str(target))
                console.print(f"Resume later with: [bold]cd {target} && smairt menu[/bold]")
                if _select(
                    "Next",
                    [(True, "Open project dashboard"), (False, "Return to shell")],
                    True,
                ):
                    run_project_menu(target)
                return target
        except BackNavigation:
            if step == 0:
                return None
            step -= 1
        except (FileExistsError, OSError, ValueError) as exc:
            console.print(f"[red]Cannot continue:[/] {exc}")


def _show_guidance(root: Path, section: str) -> None:
    """Show bounded workflow guidance rather than duplicating expert commands."""
    guidance = next_guidance(root)
    recommended = guidance.get("recommended")
    _header(f"{section}", "Status and command handoff")
    if isinstance(recommended, dict):
        console.print(f"[bold]Recommended:[/] {recommended.get('label')}")
        if recommended.get("read"):
            console.print("[bold]Read first:[/] " + " · ".join(recommended["read"]))
        if recommended.get("command"):
            console.print(f"[cyan]{recommended['command']}[/cyan]")
        console.print(
            Panel(
                render_suggested_prompt(root, guidance),
                title="Suggested Prompt",
                border_style=ORANGE,
            )
        )
        console.print("[dim]Copy again with: smairt next --prompt[/dim]")
    else:
        console.print("[cyan]smairt next --json[/cyan]")
    _pause()


def _settings_menu(root: Path) -> None:
    """Edit schema-v3 project metadata without hiding migration requirements."""
    while True:
        config = SmairtConfig.load(root / "smairt.yaml")
        _header("Project Settings", f"Schema v{config.schema_version}")
        try:
            action = _select(
                "Settings",
                [
                    ("edit", "Edit project details"),
                    ("show", "Show current settings"),
                    ("back", "Back"),
                ],
            )
            if action == "back":
                return
            if action == "show":
                console.print(config.project.model_dump(mode="json"))
                _pause()
                continue
            if config.schema_version < 3:
                console.print("Schema v3 is required for fields and license settings.")
                if not _yes_no("Apply the backed-up v2 to v3 migration now?", True):
                    continue
                apply_migration(root, config.active_contributor)
                config = SmairtConfig.load(root / "smairt.yaml")
            name = _text("Project name", config.project.name)
            author = _text("Author or researcher", config.project.author)
            question = _text("Initial question (optional)", config.project.question or "")
            description = _text("Description (optional)", config.project.description or "")
            console.print(f"[dim]Suggestions: {FIELD_SUGGESTIONS}[/dim]")
            fields_text = _text(
                "Fields of study, comma separated",
                ", ".join(config.project.fields_of_study),
            )
            license_name = _select(
                "Project license",
                [(item, item.value) for item in ProjectLicense],
                config.project.license,
            )
            if _yes_no("Save these project settings?", True):
                fields = [item.strip() for item in fields_text.split(",") if item.strip()]
                update_project_settings(
                    root,
                    name=name,
                    author=author,
                    question=question or None,
                    description=description or None,
                    fields_of_study=fields,
                    license_name=license_name,
                )
                console.print("[green]Project settings saved.[/green]")
        except BackNavigation:
            return
        except (OSError, ValueError) as exc:
            console.print(f"[red]Cannot save settings:[/] {exc}")


def _people_menu(root: Path) -> None:
    """List, add, and select contributor identities without rewriting history."""
    while True:
        config = SmairtConfig.load(root / "smairt.yaml")
        _header("People", f"Active: {config.active_contributor or 'not selected'}")
        for contributor in config.contributors:
            marker = "*" if contributor.id == config.active_contributor else " "
            console.print(f"{marker} {contributor.name} ({contributor.id})")
        try:
            action = _select(
                "People",
                [
                    ("add", "Add collaborator"),
                    ("use", "Select active contributor"),
                    ("back", "Back"),
                ],
            )
            if action == "back":
                return
            if action == "add":
                name = _text("Collaborator name")
                email = _text("Email (optional)")
                contributor = add_contributor(root, name, email or None)
                console.print(f"[green]Added {contributor.name}.[/green]")
            elif not config.contributors:
                console.print("[yellow]Add a contributor first.[/yellow]")
            else:
                selected = _select(
                    "Active contributor",
                    [(item.id, item.name) for item in config.contributors],
                    config.active_contributor,
                )
                use_contributor(root, selected)
        except BackNavigation:
            return
        except (OSError, ValueError) as exc:
            console.print(f"[red]Cannot update people:[/] {exc}")


def _environment_menu(root: Path) -> None:
    """Select no environment, an existing Conda environment, or create one."""
    config = SmairtConfig.load(root / "smairt.yaml")
    _header("Environment", f"Current: {config.environment.mode.value}")
    try:
        with console.status("Discovering local Conda environments…", spinner="dots"):
            environments = conda_environments()
        options: list[tuple[str, str]] = [("none", "No managed environment")]
        options.extend(
            (f"existing:{item['prefix']}", f"Use existing: {item['name']}") for item in environments
        )
        options.append(("new", "Create a new Conda environment"))
        options.append(("back", "Back"))
        selected = _select("Environment", options)
        if selected == "back":
            return
        if selected == "none":
            select_environment(root, mode=EnvironmentMode.NONE)
        elif selected == "new":
            name = _text("New Conda environment name", config.project.slug)
            existing_names = {str(item["name"]) for item in environments}
            if name in existing_names:
                collision = _select(
                    "That environment already exists",
                    [
                        ("use", "Use the existing environment"),
                        ("rename", "Choose another name"),
                        ("cancel", "Cancel"),
                    ],
                )
                if collision == "cancel":
                    return
                if collision == "use":
                    selected_environment = next(
                        item for item in environments if str(item["name"]) == name
                    )
                    select_environment(
                        root,
                        mode=EnvironmentMode.EXISTING_CONDA,
                        name=name,
                        prefix=str(selected_environment["prefix"]),
                    )
                    console.print("[green]Existing environment selected.[/green]")
                    return
                name = _text("Different Conda environment name", f"{config.project.slug}-2")
            with console.status("Creating Conda environment…", spinner="dots"):
                select_environment(root, mode=EnvironmentMode.NEW_CONDA, name=name, create=True)
        else:
            prefix = selected.split(":", 1)[1]
            select_environment(
                root,
                mode=EnvironmentMode.EXISTING_CONDA,
                name=Path(prefix).name,
                prefix=prefix,
            )
        console.print("[green]Environment selection saved.[/green]")
    except BackNavigation:
        return
    except (OSError, ValueError) as exc:
        console.print(f"[red]Cannot update environment:[/] {exc}")


def _integrations_menu(root: Path) -> None:
    """Bind user-local connections and explain project-specific permissions."""
    while True:
        config = SmairtConfig.load(root / "smairt.yaml")
        health = integration_health(root) if config.schema_version >= 4 else {}
        _header(
            "Project Integrations",
            "Connections are local to this machine; agent access is a separate project permission",
        )
        if health:
            _cards(
                *(
                    (
                        label,
                        (
                            "Ready"
                            if cast(dict[str, object], health[provider]).get("ready")
                            else "Not connected"
                        ),
                    )
                    for provider, label in (
                        ("zotero", "Zotero"),
                        ("openalex", "OpenAlex"),
                        ("semantic_scholar", "Semantic Scholar"),
                        ("unpaywall", "Unpaywall"),
                    )
                )
            )
        try:
            action = _select(
                "Integrations",
                [
                    ("status", "Connection summary · no network request"),
                    ("zotero", "Connect this project to a local Zotero profile"),
                    ("openalex", "Connect this project to a local OpenAlex profile"),
                    (
                        "semantic_scholar",
                        "Connect an optional Semantic Scholar key profile",
                    ),
                    ("unpaywall", "Connect an Unpaywall contact profile"),
                    ("test", "Test a connected provider now"),
                    ("agent", "Agent metadata access · never PDFs or write access"),
                    ("disconnect", "Disconnect a provider on this machine"),
                    ("back", "Back"),
                ],
            )
            if action == "back":
                return
            if config.schema_version < 5:
                console.print(
                    "Schema v5 moves connection IDs out of Git-managed project configuration."
                )
                if _yes_no("Preview and apply the backed-up privacy migration now?", True):
                    console.print(migration_plan(root))
                    if _yes_no("Apply this migration?", True):
                        apply_migration(root, config.active_contributor)
                continue
            if action in {"zotero", "openalex", "semantic_scholar", "unpaywall"}:
                provider = cast(ProviderName, action)
                profiles = provider_profiles(provider)
                choices = [(name, name) for name in profiles]
                if not choices:
                    console.print(
                        f"No local {provider.title()} profile exists. Run [bold]smairt setup[/] "
                        "first; no project file was changed."
                    )
                    _pause()
                    continue
                selected = _select(f"Local {provider.title()} profile", choices)
                profile_value = profiles[selected]
                if provider == "openalex":
                    configure_openalex(
                        root,
                        enabled=True,
                        profile=selected,
                        environment_variable=profile_value.environment_variable
                        or "OPENALEX_API_KEY",
                    )
                elif provider == "zotero":
                    configure_zotero(
                        root,
                        mode=profile_value.mode or ZoteroMode.LOCAL,
                        library_id=profile_value.library_id,
                        library_type=profile_value.library_type or ZoteroLibraryType.USER,
                        profile=selected,
                        environment_variable=profile_value.environment_variable or "ZOTERO_API_KEY",
                        mcp_access_enabled=config.integrations.zotero.mcp_access_enabled,
                        confirm_agent_access=False,
                    )
                else:
                    bind_profile(root, provider, selected)
                console.print(
                    f"[green]{provider.title()} connected for this checkout.[/] "
                    "Connection IDs remain outside the project repository."
                )
            elif action == "status":
                _render_integration_health(health)
            elif action == "test":
                provider = _select(
                    "Connected provider",
                    [
                        ("zotero", "Zotero"),
                        ("openalex", "OpenAlex"),
                        ("semantic_scholar", "Semantic Scholar"),
                        ("unpaywall", "Unpaywall"),
                    ],
                )
                provider_name = provider
                binding = load_bindings(root).providers.get(provider_name)
                if not binding:
                    raise ValueError(f"{provider.title()} is not connected on this machine")
                console.print(_connection_receipt(test_profile(provider_name, binding)))
            elif action == "disconnect":
                provider = _select(
                    "Provider",
                    [
                        ("zotero", "Zotero"),
                        ("openalex", "OpenAlex"),
                        ("semantic_scholar", "Semantic Scholar"),
                        ("unpaywall", "Unpaywall"),
                    ],
                )
                if provider == "openalex":
                    default_profile = provider_profiles("openalex").get("default")
                    configure_openalex(
                        root,
                        enabled=False,
                        profile="default",
                        environment_variable=(
                            (default_profile.environment_variable or "OPENALEX_API_KEY")
                            if default_profile
                            else "OPENALEX_API_KEY"
                        ),
                    )
                elif provider == "zotero":
                    configure_zotero(
                        root,
                        mode=ZoteroMode.DISABLED,
                        library_id=None,
                        library_type=ZoteroLibraryType.USER,
                        profile="default",
                        mcp_access_enabled=False,
                    )
                else:
                    unbind_profile(root, provider)
                console.print(f"[green]{provider.title()} disconnected for this checkout.[/green]")
            else:
                zotero_status = cast(dict[str, object], integration_health(root)["zotero"])
                if not zotero_status.get("ready"):
                    raise ValueError(
                        "connect a Zotero profile before enabling agent metadata access"
                    )
                profile_name = str(zotero_status["bound_profile"])
                profile_value = provider_profiles("zotero")[profile_name]
                enable = _yes_no(
                    "Allow the configured assistant to read bounded Zotero metadata only?",
                    not config.integrations.zotero.mcp_access_enabled,
                )
                confirm_private = (
                    _yes_no(
                        "Confirm this private-project permission for the active contributor?", False
                    )
                    if enable and config.data.classification is DataClassification.PRIVATE
                    else False
                )
                configure_zotero(
                    root,
                    mode=profile_value.mode or ZoteroMode.LOCAL,
                    library_id=profile_value.library_id,
                    library_type=profile_value.library_type or ZoteroLibraryType.USER,
                    profile=profile_name,
                    environment_variable=profile_value.environment_variable or "ZOTERO_API_KEY",
                    mcp_access_enabled=enable,
                    confirm_agent_access=confirm_private,
                )
                harness = config.harness.active
                if enable:
                    configure_mcp(root, harness, True)
                console.print(
                    "[green]Agent metadata access updated.[/] PDFs, full text, secrets, and "
                    "write operations remain unavailable."
                )
        except BackNavigation:
            return
        except (OSError, RuntimeError, ValueError) as exc:
            console.print(f"[red]Cannot update integration:[/] {exc}")
        _pause()


def _render_integration_health(payload: dict[str, object]) -> None:
    """Explain local connection state without dumping internal dictionaries."""
    for provider in ("zotero", "openalex", "semantic_scholar", "unpaywall"):
        status_payload = cast(dict[str, object], payload[provider])
        ready = bool(status_payload.get("ready"))
        console.print(
            f"{'[green]✓[/]' if ready else '[yellow]![/]'} "
            f"{provider.replace('_', ' ').title()}: "
            f"{'ready' if ready else 'not connected on this machine'}"
        )
        if status_payload.get("bound_profile"):
            console.print(f"  Local profile: {status_payload['bound_profile']}")
        if provider == "zotero":
            console.print(
                "  Agent access: "
                + ("metadata only" if status_payload.get("mcp_access_enabled") else "disabled")
            )
        if provider == "semantic_scholar":
            console.print(f"  Access: {status_payload.get('access_mode', 'public')}")


def _zotero_item_label(raw: dict[str, Any]) -> str:
    """Render useful Zotero identity while deliberately hiding internal keys."""
    item = public_item(raw)
    creators = cast(list[dict[str, object]], item.get("creators") or [])
    creator = creators[0] if creators else {}
    author = str(creator.get("lastName") or creator.get("name") or "Unknown author")
    year_match = re.search(r"\b(\d{4})\b", str(item.get("date") or ""))
    year = year_match.group(1) if year_match else "n.d."
    title = str(item.get("title") or "Untitled item")
    return f"{title} · {author} · {year}"


def _zotero_key(raw: dict[str, Any], label: str) -> str:
    """Extract an internal key only after a human-facing selection."""
    item = public_item(raw)
    key = item.get("key")
    if not isinstance(key, str) or not key:
        raise ValueError(f"selected Zotero {label} has no usable internal key")
    return key


def _choose_zotero_collection(provider: ZoteroProvider) -> tuple[str, str]:
    """Select one collection by name without exposing its key."""
    collections = provider.collections(50)
    choices: list[tuple[str, str]] = []
    for raw in collections:
        data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
        key = raw.get("key") or cast(dict[str, Any], data).get("key")
        name = cast(dict[str, Any], data).get("name") or "Unnamed collection"
        if isinstance(key, str) and key:
            choices.append((key, str(name)))
    if not choices:
        raise ValueError("no Zotero collections were found")
    key = _select("Zotero collection", sorted(choices, key=lambda item: item[1].casefold()))
    return key, next(name for value, name in choices if value == key)


def _choose_zotero_item(root: Path) -> tuple[ZoteroProvider, str]:
    """Discover and select a Zotero item through search, collections, or recency."""
    provider = ZoteroProvider(root)
    method = _select(
        "Find a Zotero item",
        [
            ("search", "Search title, author, or tag"),
            ("collection", "Browse a named collection"),
            ("recent", "Browse 25 recent items"),
            ("back", "Back"),
        ],
    )
    if method == "back":
        raise BackNavigation()
    if method == "search":
        items = provider.search(_text("Title, author, or tag"), 20)
    elif method == "collection":
        collection_key, _ = _choose_zotero_collection(provider)
        items = provider.collection_items(collection_key, 100)
    else:
        items = provider.recent(25)
    top_level = [
        raw
        for raw in items
        if public_item(raw).get("itemType") not in {"attachment", "note", "annotation"}
    ]
    if not top_level:
        raise ValueError("no matching top-level Zotero items were found")
    key = _select(
        "Zotero item",
        [(_zotero_key(raw, "item"), _zotero_item_label(raw)) for raw in top_level],
    )
    return provider, key


def _choose_zotero_attachment(provider: ZoteroProvider, item_key: str) -> str:
    """Choose one local PDF child by filename rather than attachment key."""
    if provider.config.mode is not ZoteroMode.LOCAL:
        raise ValueError("copying PDFs requires the local Zotero app connection")
    children = [public_item(raw) for raw in provider.children(item_key, 50)]
    pdfs = [
        child
        for child in children
        if child.get("itemType") == "attachment"
        and (
            str(child.get("contentType") or "").lower() == "application/pdf"
            or str(child.get("filename") or "").lower().endswith(".pdf")
        )
    ]
    if not pdfs:
        raise ValueError("the selected Zotero item has no local PDF attachment")
    return _select(
        "PDF attachment",
        [
            (str(child["key"]), str(child.get("filename") or "PDF attachment"))
            for child in pdfs
            if child.get("key")
        ],
    )


def _literature_provider(root: Path, *, allow_both: bool) -> str:
    """Choose a discovery index and explain when setup is actually required."""
    openalex_ready = bool(
        cast(dict[str, object], integration_health(root)["openalex"]).get("ready")
    )
    choices: list[tuple[str, str]] = [
        (
            "semantic-scholar",
            "Semantic Scholar · relevance search, citation trails, and recommendations",
        )
    ]
    if openalex_ready:
        choices.insert(0, ("openalex", "OpenAlex · broad coverage and citation graph"))
        if allow_both:
            choices.insert(0, ("all", "Both · merge and deduplicate both indexes"))
    else:
        console.print(
            "[dim]Semantic Scholar public discovery needs no setup. Connect OpenAlex under "
            "Tools & compute → Integrations to search both indexes.[/dim]"
        )
    return _select("Discovery provider", choices, "all" if openalex_ready and allow_both else None)


def _browse_literature_candidates(root: Path, candidates: list[LiteratureCandidate]) -> None:
    """Inspect provisional results and import DOI-backed choices through authoritative metadata."""
    if not candidates:
        console.print("No matching literature candidates were returned.")
        return
    while True:
        selected = _select(
            "Provisional result",
            [
                (
                    index,
                    f"{item.title} · {(item.authors or ['Unknown author'])[0]} · "
                    f"{item.year or 'n.d.'} · {item.provider.replace('_', ' ').title()}",
                )
                for index, item in enumerate(candidates)
            ]
            + [("back", "Back")],
        )
        if selected == "back":
            return
        item = candidates[cast(int, selected)]
        console.print(
            Panel(
                f"[bold]{item.title}[/]\n"
                f"Authors: {', '.join(item.authors) or 'not reported'}\n"
                f"Year: {item.year or 'n.d.'} · Venue: {item.venue or 'not reported'}\n"
                f"DOI: {item.doi or 'not available'} · Citations: "
                f"{item.cited_by_count if item.cited_by_count is not None else 'not reported'}\n"
                f"Abstract: {'available' if item.abstract_available else 'not reported'}\n"
                f"Provider URL: {item.url or 'not reported'}",
                title=f"{item.provider.replace('_', ' ').title()} · provisional",
                border_style=ORANGE,
            )
        )
        if not item.doi:
            _select(
                "This result has no DOI and cannot be imported automatically",
                [("back", "Back to results")],
            )
            continue
        action = _select(
            "Candidate action",
            [
                ("import", "Import DOI through Crossref/DataCite"),
                ("back", "Back to results"),
            ],
        )
        if action == "import" and _yes_no("Import authoritative metadata for this DOI?", False):
            record = add_doi_reference(
                root,
                item.doi,
                confirm_remote=_yes_no("Send this DOI in a metadata request?", True),
            )
            _reference_receipt(root, [record], "Authoritative DOI metadata imported; no PDF added")


def _references_menu(root: Path) -> None:
    """Separate metadata, documents, and human verification with visible receipts."""
    while True:
        records = load_index(root)
        verified = sum(item.verification_status.value == "verified" for item in records)
        attached = sum(bool(item.local_path) for item in records)
        _header("References", "Add metadata → attach PDFs → review and verify")
        _cards(
            ("Indexed", len(records)),
            ("PDFs attached", attached),
            ("Human verified", verified),
        )
        try:
            action = _select(
                "References",
                [
                    ("metadata", "Add metadata · DOI or Zotero"),
                    ("discover", "Discover literature · search, citation trails, or OA copy"),
                    ("document", "Add a local PDF · standalone or attach"),
                    ("review", "Review, edit, and human-verify metadata"),
                    ("zotero-pdf", "Copy one selected local Zotero PDF"),
                    ("export", "Export references"),
                    ("back", "Back"),
                ],
            )
            if action == "back":
                return
            if action == "metadata":
                source = _select(
                    "Metadata source",
                    [
                        ("doi", "DOI · Crossref metadata, no PDF"),
                        ("zotero-item", "Find one Zotero item · metadata only"),
                        ("zotero-collection", "Browse a Zotero collection · metadata only"),
                        ("back", "Back"),
                    ],
                )
                if source == "back":
                    continue
                if source == "doi":
                    record = add_doi_reference(
                        root,
                        _text("DOI"),
                        use_openalex=_yes_no(
                            "Supplement missing fields with connected OpenAlex?", False
                        ),
                        confirm_remote=_yes_no("Send this DOI in a metadata request?", True),
                    )
                    _reference_receipt(root, [record], "Metadata imported; no PDF was added")
                elif source == "zotero-item":
                    _, item_key = _choose_zotero_item(root)
                    record = import_zotero_item(root, item_key)
                    _reference_receipt(
                        root,
                        [record],
                        "Zotero metadata imported; the item key is retained as source provenance",
                    )
                else:
                    provider = ZoteroProvider(root)
                    key, collection_name = _choose_zotero_collection(provider)
                    preview = provider.collection_items(key, 101)
                    truncated = len(preview) > 100
                    console.print(
                        f"{collection_name}: {min(len(preview), 100)} item(s) will be considered "
                        + ("(additional items will be left unchanged)." if truncated else "")
                    )
                    if not _yes_no("Import this collection metadata?", False):
                        continue
                    imported = import_zotero_collection(root, key, limit=100)
                    _reference_receipt(
                        root,
                        imported,
                        "Collection metadata imported; PDFs were not copied",
                    )
            elif action == "discover":
                discovery = _select(
                    "Discover literature",
                    [
                        ("search", "Search papers · OpenAlex, Semantic Scholar, or both"),
                        ("references", "Works referenced by an indexed DOI"),
                        ("cited-by", "Works citing an indexed DOI"),
                        ("recommend", "Recommended papers from an indexed DOI"),
                        ("access", "Find an open-access copy"),
                        ("back", "Back"),
                    ],
                )
                if discovery == "back":
                    continue
                if discovery == "search":
                    discovery_provider = _literature_provider(root, allow_both=True)
                    confirm_remote = _yes_no(
                        "Send this search query to a remote literature provider?", True
                    )
                    candidates = literature_search(
                        root,
                        _text("Search query"),
                        20,
                        provider=discovery_provider,
                        confirm_remote=confirm_remote,
                    )
                    _browse_literature_candidates(root, candidates)
                else:
                    eligible = [record for record in records if record.doi]
                    if not eligible:
                        raise ValueError("add a DOI-backed reference before using this discovery")
                    identifier = _select(
                        "Reference",
                        [
                            (record.id, f"{record.title} · {record.year or 'n.d.'}")
                            for record in eligible
                        ],
                    )
                    confirm_remote = _yes_no(
                        "Send this reference identifier to a remote literature provider?", True
                    )
                    if discovery in {"references", "cited-by"}:
                        discovery_provider = _literature_provider(root, allow_both=False)
                        candidates = literature_related(
                            root,
                            identifier,
                            discovery,
                            20,
                            provider=discovery_provider,
                            confirm_remote=confirm_remote,
                        )
                        _browse_literature_candidates(root, candidates)
                    elif discovery == "recommend":
                        _browse_literature_candidates(
                            root,
                            literature_recommend(
                                root, identifier, 20, confirm_remote=confirm_remote
                            ),
                        )
                    else:
                        access_preview = literature_access(root, identifier)
                        location = cast(dict[str, object], access_preview["location"])
                        console.print(
                            f"Source: {location.get('host')} · "
                            f"License: {location.get('license') or 'not reported'} · "
                            f"Version: {location.get('version') or 'not reported'}\n"
                            f"URL: {location.get('url')}"
                        )
                        if location.get("direct_pdf") and _yes_no(
                            "Download and validate this PDF into the project?", False
                        ):
                            console.print(
                                literature_access(root, identifier, download=True, confirmed=True)
                            )
            elif action == "document":
                document_action = _select(
                    "Local PDF",
                    [
                        ("standalone", "Index a PDF as a new reference"),
                        ("attach", "Attach a PDF to existing metadata"),
                    ],
                )
                pdf = Path(_text("PDF path")).expanduser()
                if document_action == "standalone":
                    proposed = inspect_pdf(pdf)
                    console.print(
                        f"Proposed title: {proposed['title']}\n"
                        f"Proposed DOI: {proposed.get('doi') or 'not detected'}"
                    )
                    title = _text("Confirmed title", str(proposed["title"]))
                    if not _yes_no("Copy and index this PDF in the project?", True):
                        continue
                    record = add_reference(
                        root,
                        pdf,
                        title=title,
                        authors=list(cast(list[str], proposed.get("authors", []))),
                        doi=cast(str | None, proposed.get("doi")),
                    )
                else:
                    if not records:
                        raise ValueError("add metadata before attaching a PDF")
                    attachable = [item for item in records if not item.local_path]
                    if not attachable:
                        raise ValueError("all indexed references already have PDFs attached")
                    identifier = _select(
                        "Reference",
                        [(item.id, f"{item.title} · {item.id}") for item in attachable],
                    )
                    record = attach_reference(root, identifier, pdf)
                _reference_receipt(root, [record], "PDF copied, validated, and checksummed")
            elif action == "review":
                if not records:
                    console.print("No references are indexed yet.")
                    _pause()
                    continue
                identifier = _select(
                    "Reference",
                    [
                        (item.id, f"{item.title} · {item.verification_status.value}")
                        for item in records
                    ],
                )
                record = next(item for item in records if item.id == identifier)
                console.print(
                    Panel(
                        f"[bold]{record.title}[/]\n"
                        f"Authors: {', '.join(record.authors) or 'missing'}\n"
                        f"Year: {record.year or 'missing'} · DOI: {record.doi or 'missing'}\n"
                        f"PDF: {record.local_path or 'not attached'}\n"
                        f"Status: {record.verification_status.value}",
                        title=record.id,
                    )
                )
                review_action = _select(
                    "Review action",
                    [
                        ("verify", "Confirm current metadata"),
                        ("edit", "Correct one field"),
                        ("back", "Back"),
                    ],
                )
                if review_action == "back":
                    continue
                contributor = SmairtConfig.load(root / "smairt.yaml").active_contributor
                if not contributor:
                    raise ValueError("select an active contributor before attributed review")
                if review_action == "verify":
                    record = verify_reference(root, identifier, contributor)
                else:
                    field = _select(
                        "Field",
                        [
                            (item, item.title())
                            for item in ("title", "authors", "year", "doi", "venue", "url")
                        ],
                    )
                    record = edit_reference(
                        root, identifier, field, _text("Corrected value"), contributor
                    )
                _reference_receipt(
                    root, [record], "Human review recorded with contributor attribution"
                )
            elif action == "zotero-pdf":
                provider, item_key = _choose_zotero_item(root)
                attachment_key = _choose_zotero_attachment(provider, item_key)
                if not _yes_no(
                    "Copy this selected PDF into references/pdfs and record its checksum?", False
                ):
                    continue
                record = copy_zotero_attachment(root, item_key, attachment_key, confirmed=True)
                _reference_receipt(
                    root, [record], "Selected Zotero PDF copied; no other attachment changed"
                )
            else:
                console.print(
                    "Export from the shell for an explicit destination:\n"
                    "  smairt reference export --format bibtex --output references.bib\n"
                    "  smairt reference export --format csl-json --output references.json"
                )
        except BackNavigation:
            return
        except (OSError, RuntimeError, ValueError) as exc:
            console.print(f"[red]Cannot update references:[/] {exc}")
        _pause()


def _reference_receipt(root: Path, records: list[Any], effect: str) -> None:
    """Show exactly what a reference operation changed and where it is visible."""
    lines = [f"[green]{effect}[/green]", f"Records changed: {len(records)}"]
    for record in records[:10]:
        lines.append(
            f"• {record.id} · {record.verification_status.value} · "
            f"PDF: {record.local_path or 'none'}"
        )
    if len(records) > 10:
        lines.append(f"…and {len(records) - 10} more")
    lines.extend(
        [
            "Index: references/index.yaml",
            "Provider receipts: references/provenance/",
            "Next: review metadata and record human verification",
        ]
    )
    console.print(Panel("\n".join(lines), title="Reference receipt", border_style="green"))


def _health_menu(root: Path) -> None:
    """Separate blocking health, recommended updates, and recovery."""
    while True:
        report = doctor(root)
        validation = cast(dict[str, object], report["validation"])
        _header(
            "Health & updates",
            str(report["health_state"]).replace("_", " ").title(),
        )
        updates = cast(dict[str, object], report["recommended_updates"])
        _cards(
            ("Health", "Working" if report["ok"] else "Blocked"),
            ("Updates", "Available" if updates["updates_available"] else "Current"),
        )
        try:
            action = _select(
                "Health & updates",
                [
                    ("validate", "Validate project records"),
                    ("doctor", "Doctor · blocking problems and exact solutions"),
                    ("updates", "Project updates · preview schema, guidance, and adapter"),
                    ("recovery", "Recovery · interrupted transactions and technical repair"),
                ],
            )
            if action == "validate":
                _render_validation(validation)
            elif action == "doctor":
                _render_doctor(report)
            elif action == "updates":
                plan = project_update_plan(root)
                _render_update_plan(plan)
                if plan["updates_available"] and _yes_no(
                    "Apply all conflict-free updates shown above?", False
                ):
                    receipt = apply_project_updates(
                        root,
                        contributor_id=SmairtConfig.load(root / "smairt.yaml").active_contributor,
                    )
                    _render_update_plan(cast(dict[str, object], receipt["final"]))
                    console.print("[green]Project updates completed.[/green]")
            else:
                _recovery_menu(root)
            _pause()
        except BackNavigation:
            return
        except (OSError, RuntimeError, ValueError) as exc:
            console.print(f"[red]Health check could not continue:[/] {exc}")
            _pause()


def _render_validation(payload: dict[str, object]) -> None:
    """Render pass/warn/fail validation without implementation-shaped output."""
    findings = cast(list[dict[str, str]], payload.get("findings", []))
    if payload["ok"] and not findings:
        console.print("[green]✓ All project checks passed.[/green]")
        return
    errors = [item for item in findings if item.get("severity") == "error"]
    warnings = [item for item in findings if item.get("severity") != "error"]
    console.print(f"[red]{len(errors)} error(s)[/] · [yellow]{len(warnings)} warning(s)[/]")
    for item in findings:
        marker = "[red]FAIL[/]" if item.get("severity") == "error" else "[yellow]WARN[/]"
        console.print(f"{marker} {item.get('message')} [dim]({item.get('artifact')})[/dim]")


def _render_doctor(payload: dict[str, object]) -> None:
    """Group doctor output by researcher-facing subsystem."""
    console.print(
        "[green]✓ Doctor found no blocking problem.[/]"
        if payload["ok"]
        else "[red]Doctor found blocking problems.[/]"
    )
    categories = {
        "Package": not cast(dict[str, object], payload["package"])["missing_dependencies"],
        "Project": cast(dict[str, object], payload["validation"])["ok"],
        "Git": cast(dict[str, object], payload["git"])["healthy"],
        "Environment": cast(dict[str, object], payload["environment"])["healthy"],
        "Transactions": cast(dict[str, object], payload["transactions"])["ok"],
    }
    for label, ready in categories.items():
        console.print(f"{'[green]✓[/]' if ready else '[yellow]![/]'} {label}")
    for warning in cast(list[str], payload.get("warnings", [])):
        console.print(f"[yellow]Suggested action:[/] {warning}")
    updates = cast(dict[str, object], payload["recommended_updates"])
    if updates["updates_available"]:
        console.print("[cyan]Recommended:[/] Open Health & updates → Project updates.")


def _render_update_plan(payload: dict[str, object]) -> None:
    """Explain each update layer and its effect without raw implementation data."""
    schema = cast(dict[str, object], payload["project_schema"])
    guidance = cast(dict[str, object], payload["managed_guidance"])
    adapter = cast(dict[str, object], payload["harness_adapter"])
    console.print(
        f"Project schema: {schema['current']} → {schema['target']} "
        f"({'update available' if schema['status'] == 'available' else 'current'})"
    )
    for step in cast(list[dict[str, int]], schema["steps"]):
        console.print(f"  • v{step['from_version']} → v{step['to_version']} · backed up first")
    console.print(
        f"Managed guidance: {guidance['status']} · "
        f"{len(cast(list[object], guidance['changes']))} change(s)"
    )
    console.print(
        f"{str(adapter['active']).title()} adapter: {adapter['status']} · "
        f"recorded {adapter['recorded']}, installed {adapter['installed']}, "
        f"target {adapter['target']}"
    )
    for blocker in cast(list[str], payload.get("blockers", [])):
        console.print(f"[red]Blocked:[/] {blocker}")


def _project_setup_menu(root: Path) -> None:
    """Group editable project setup without mixing it with user-wide setup."""
    while True:
        try:
            action = _select(
                "Project setup",
                [
                    ("settings", "Project details and license"),
                    ("people", "People and active contributor"),
                    ("environment", "Conda environment"),
                    ("integrations", "Local connections and project permissions"),
                    ("back", "Back"),
                ],
            )
            if action == "back":
                return
            if action == "settings":
                _settings_menu(root)
            elif action == "people":
                _people_menu(root)
            elif action == "environment":
                _environment_menu(root)
            else:
                _integrations_menu(root)
        except BackNavigation:
            return


def _advanced_menu(root: Path) -> None:
    """Expose real safety, harness, migration, and recovery operations."""
    while True:
        config = SmairtConfig.load(root / "smairt.yaml")
        _header("Advanced", "Safety, harness adapters, migrations, and recovery")
        try:
            action = _select(
                "Advanced",
                [
                    ("safety", "Safety and sharing policy"),
                    ("harness", "Coding harness adapter"),
                    ("migration", "Schema migration status"),
                    ("recovery", "Recovery and technical commands"),
                    ("back", "Back"),
                ],
            )
            if action == "back":
                return
            if action == "safety":
                console.print(safety_status(root))
                safety_action = _select(
                    "Safety",
                    [
                        ("mode", "Change Standard or Strict mode"),
                        ("release", "Run sharing and release checks"),
                        ("back", "Back"),
                    ],
                )
                if safety_action == "mode":
                    mode = _select("Safety mode", [("standard", "Standard"), ("strict", "Strict")])
                    if _yes_no(f"Change project safety mode to {mode}?", False):
                        console.print(set_safety_mode(root, mode))
                elif safety_action == "release":
                    _render_validation(release_check(root))
            elif action == "harness":
                _render_harness_chooser(config.harness.active)
                selected = _select(
                    "Active harness",
                    [(item, HARNESS_PRESENTATIONS[item].display_name) for item in HarnessName],
                    config.harness.active,
                )
                if selected != config.harness.active and _yes_no(
                    f"Switch the managed adapter to {selected.value}?", False
                ):
                    console.print(select_harness(root, selected.value))
            elif action == "migration":
                console.print(migration_plan(root))
            else:
                console.print(
                    "Recovery remains explicit to protect user-authored work:\n"
                    "  smairt recovery status --json\n"
                    "  smairt recovery complete <transaction-id> --yes\n"
                    "  smairt recovery rollback <transaction-id> --yes\n"
                    "Technical reports: smairt doctor --json · smairt validate --json"
                )
            _pause()
        except BackNavigation:
            return
        except (OSError, RuntimeError, ValueError) as exc:
            console.print(f"[red]Advanced action could not continue:[/] {exc}")
            _pause()


def _recovery_menu(root: Path) -> None:
    """Explain explicit recovery commands without silently changing researcher work."""
    del root
    console.print(
        "Recovery protects user-authored work and always requires a transaction ID:\n"
        "  smairt recovery status --json\n"
        "  smairt recovery complete <transaction-id> --yes\n"
        "  smairt recovery rollback <transaction-id> --yes\n"
        "Technical reports: smairt doctor --json · smairt validate --json"
    )


def _tools_menu(root: Path) -> None:
    """Group local environment, harness, connection, and optional compute setup."""
    while True:
        config = SmairtConfig.load(root / "smairt.yaml")
        _header("Tools & compute", "Local execution remains the default; HPC is optional")
        try:
            action = _select(
                "Tools & compute",
                [
                    ("environment", "Local Conda environment"),
                    ("harness", "AI coding harness adapter"),
                    ("connections", "Bind local literature connections to this checkout"),
                    ("hpc", "HPC/Slurm · inspect optional execution setup"),
                ],
            )
            if action == "environment":
                _environment_menu(root)
            elif action == "connections":
                _integrations_menu(root)
            elif action == "hpc":
                console.print(
                    "HPC is optional for large analyses and is never used by the demo.\n"
                    "Configure a machine-local profile with 'smairt setup', then inspect with\n"
                    "'smairt hpc status'. SMAIRT stores no SSH password or private key."
                )
                _pause()
            else:
                _render_harness_chooser(config.harness.active)
                selected = _select(
                    "Active harness",
                    [(item, HARNESS_PRESENTATIONS[item].display_name) for item in HarnessName],
                    config.harness.active,
                )
                if selected != config.harness.active and _yes_no(
                    f"Switch the managed adapter to {selected.value}?", False
                ):
                    console.print(select_harness(root, selected.value))
                    _pause()
        except BackNavigation:
            return
        except (OSError, RuntimeError, ValueError) as exc:
            console.print(f"[red]Tool setup could not continue:[/] {exc}")
            _pause()


def _sharing_menu(root: Path) -> None:
    """Keep scientific safety policy separate from ordinary project health."""
    while True:
        config = SmairtConfig.load(root / "smairt.yaml")
        _header("Safety & sharing", f"Current safety mode: {config.safety_mode.value}")
        try:
            action = _select(
                "Safety & sharing",
                [
                    ("status", "Explain current safety policy"),
                    ("mode", "Change Standard or Strict mode"),
                    ("sharing", "Check readiness to share or release"),
                ],
            )
            if action == "status":
                console.print(safety_status(root))
            elif action == "sharing":
                _render_validation(release_check(root))
            else:
                mode = _select("Safety mode", [("standard", "Standard"), ("strict", "Strict")])
                if _yes_no(f"Change project safety mode to {mode}?", False):
                    console.print(set_safety_mode(root, mode))
            _pause()
        except BackNavigation:
            return
        except (OSError, RuntimeError, ValueError) as exc:
            console.print(f"[red]Safety check could not continue:[/] {exc}")
            _pause()


def run_project_menu(root: Path) -> None:
    """Run the nested project workflow hub directly beneath the shell prompt."""
    root = root.resolve()
    while True:
        config = SmairtConfig.load(root / "smairt.yaml")
        current = status(root)
        validation = current["validation"]
        _header(
            config.project.name,
            f"{'Healthy' if validation['ok'] else 'Needs attention'} · "
            f"Contributor: {config.active_contributor or 'not selected'} · Esc goes back",
        )
        guidance = next_guidance(root)
        reference_count = cast(dict[str, object], current["counts"]).get("references", 0)
        integration = integration_health(root) if config.schema_version >= 4 else {}
        ready_connections = (
            sum(
                bool(cast(dict[str, object], integration[name]).get("ready"))
                for name in ("zotero", "openalex", "semantic_scholar", "unpaywall")
            )
            if integration
            else 0
        )
        _cards(
            ("Workflow", str(guidance["stage"]).replace("_", " ").title()),
            ("References", f"{reference_count} indexed"),
            ("Tools", f"{config.environment.mode.value} · {ready_connections} ready"),
            ("Health", "Healthy" if validation["ok"] else "Needs attention"),
        )
        try:
            action = _select(
                "What would you like to do?",
                [
                    ("next", "Continue research · recommended action and prompt"),
                    ("palette", "Find an action · type to filter commands and options"),
                    ("references", "Literature & references"),
                    ("setup", "Project & people"),
                    ("tools", "Tools & compute"),
                    ("health", "Health & updates"),
                    ("sharing", "Safety & sharing"),
                    ("exit", "Return to shell"),
                ],
            )
        except BackNavigation:
            return
        if action == "exit":
            return
        if action == "palette":
            try:
                action = _command_palette()
            except BackNavigation:
                continue
            except ValueError as exc:
                console.print(f"[yellow]{exc}[/yellow]")
                _pause()
                continue
            if action == "exit":
                return
        if action == "next":
            _show_guidance(root, "Continue Research")
        elif action == "references":
            _references_menu(root)
        elif action == "setup":
            _project_setup_menu(root)
        elif action == "tools":
            _tools_menu(root)
        elif action == "health":
            _health_menu(root)
        else:
            _sharing_menu(root)


def run_setup_menu() -> None:
    """Configure SMAIRT through four researcher-facing setup categories."""
    while True:
        health = setup_doctor(check_github=False)
        setup = load_user_setup()
        profile_count = sum(len(profiles) for profiles in setup.profiles.values())
        backend = keyring_health()
        _header("SMAIRT Setup", "User-wide settings · secrets never enter project files")
        _cards(
            ("Installation", "Ready" if health["ok"] else "Needs attention"),
            ("Literature", f"{profile_count} connection(s)"),
            ("Compute", f"{len(setup.compute_profiles)} profile(s)"),
            ("Appearance", f"{setup.appearance.theme} · {setup.appearance.mark}"),
        )
        try:
            action = _select(
                "Setup",
                [
                    ("installation", "Installation & version · checks and exact solutions"),
                    ("literature", "Literature connections · provider, key, test, remove"),
                    ("compute", "Compute connections · optional Slurm profiles"),
                    ("appearance", "Appearance · theme, secondary mark, and motion"),
                    ("exit", "Return to shell"),
                ],
            )
            if action == "exit":
                return
            if action == "installation":
                _render_setup_health(health)
                console.print(f"Credential backend: {backend.get('status', 'unknown')}")
            elif action == "literature":
                _literature_setup_menu()
            elif action == "compute":
                _configure_hpc_setup()
            elif action == "appearance":
                _appearance_menu()
            _pause()
        except BackNavigation:
            return
        except (OSError, RuntimeError, ValueError) as exc:
            console.print(f"[red]Setup could not continue:[/] {exc}")
            _pause()


def _literature_setup_menu() -> None:
    """Keep provider configuration, credentials, testing, and removal together."""
    while True:
        profiles = iter_profiles()
        _header("Literature connections", "Keys stay in the OS keyring; profiles stay local")
        _cards(("Configured", len(profiles)), ("Project data", "No secrets"))
        try:
            action = _select(
                "Literature provider",
                [
                    ("zotero", "Zotero · search your library; local PDFs need no plugin"),
                    ("openalex", "OpenAlex · broad search and citation graph · free key"),
                    (
                        "semantic",
                        "Semantic Scholar · search, citation trails, and recommendations",
                    ),
                    ("unpaywall", "Unpaywall · lawful OA locations · contact email"),
                    ("profiles", "Review, test, or remove configured connections"),
                ],
            )
            if action == "zotero":
                _configure_zotero_setup()
            elif action == "openalex":
                _configure_openalex_setup()
            elif action == "semantic":
                _configure_semantic_scholar_setup()
            elif action == "unpaywall":
                name = _text("Profile name", "default")
                email = _text("Contact email required by Unpaywall")
                configure_profile(
                    name, ConnectionProfile(provider="unpaywall", contact_email=email)
                )
                console.print("[green]Unpaywall contact saved locally.[/green]")
            elif not profiles:
                console.print("No literature connections are configured.")
            else:
                selected = _select(
                    "Connection profile",
                    [
                        (
                            (provider, name),
                            f"{provider.replace('_', ' ').title()} · {name}",
                        )
                        for provider, name, _profile in profiles
                    ],
                )
                operation = _select(
                    "Connection",
                    [("test", "Test connection"), ("delete", "Remove profile and stored key")],
                )
                if operation == "test":
                    provider, name = selected
                    console.print(_connection_receipt(test_profile(provider, name)))
                else:
                    provider, name = selected
                    if not _yes_no(
                        f"Remove local {provider.replace('_', ' ')} connection '{name}'?",
                        False,
                    ):
                        continue
                    profile = provider_profiles(provider)[name]
                    delete_profile(provider, name)
                    if profile.provider != "unpaywall":
                        delete_credential(profile.provider, profile.credential_profile)
                    console.print("[green]Local connection removed.[/green]")
            _pause()
        except BackNavigation:
            return


def _appearance_menu() -> None:
    """Configure and preview machine-local terminal appearance."""
    global _APPEARANCE_PREVIEW
    setup = load_user_setup()
    appearance = setup.appearance.model_copy(deep=True)
    action = _select(
        "Appearance",
        [
            ("theme", "Color theme · preview a named palette"),
            ("mark", "Secondary mark · SMAIRT always remains visible"),
            ("motion", "Motion · automatic or off"),
            ("preview", "Preview current appearance"),
            ("back", "Back"),
        ],
    )
    if action == "back":
        return
    if action == "theme":
        appearance.theme = _select(
            "Theme",
            [
                ("scientific", "Scientific console · orange and cyan"),
                ("pnnl", "PNNL inspired · orange and slate"),
                ("utep", "UTEP inspired · orange and navy"),
                ("matrix", "Matrix · green phosphor"),
                ("dracula", "Dracula · pink and cyan"),
                ("nord", "Nord · cool blue"),
                ("solarized", "Solarized · gold and teal"),
                ("amber", "Amber terminal"),
                ("high-contrast", "High contrast"),
                ("monochrome", "Monochrome"),
                ("custom", "Custom RGB accents"),
            ],
            appearance.theme,
        )
        if appearance.theme == "custom":
            appearance.primary_color = _text("Primary #RRGGBB", appearance.primary_color or ORANGE)
            appearance.secondary_color = _text(
                "Secondary #RRGGBB", appearance.secondary_color or CYAN
            )
    elif action == "mark":
        appearance.mark = _select(
            "Secondary mark",
            [
                ("none", "None · SMAIRT wordmark only"),
                ("custom", "Custom sanitized ASCII mark"),
            ],
            appearance.mark,
        )
        if appearance.mark == "custom":
            source = Path(_text("ASCII logo file")).expanduser()
            save_custom_logo(source.read_text(encoding="utf-8"))
    elif action == "motion":
        appearance.motion = _select(
            "Motion",
            [
                ("automatic", "Automatic · one launch flourish when supported"),
                ("off", "Off · static interface"),
            ],
            appearance.motion,
        )
    _APPEARANCE_PREVIEW = appearance
    try:
        _header(
            "Appearance preview",
            "Named palettes are informal easter eggs · custom marks remain local",
        )
        _cards(("Theme", appearance.theme), ("Motion", appearance.motion))
        if (
            _select(
                "Preview",
                [
                    ("apply", "Apply on this machine"),
                    ("cancel", "Cancel changes"),
                    ("back", "Back"),
                ],
            )
            == "apply"
        ):
            setup.appearance = appearance
            save_user_setup(setup)
            console.print("[green]Appearance saved on this machine.[/green]")
    finally:
        _APPEARANCE_PREVIEW = None


def _render_setup_health(payload: dict[str, object]) -> None:
    """Render setup doctor as a compact checklist instead of a raw dictionary."""
    console.print(
        "[green]All required tools are ready.[/green]"
        if payload["ok"]
        else "[yellow]Setup needs attention.[/yellow]"
    )
    for label in ("python", "git", "uv", "conda", "github_cli", "credential_backend"):
        value = payload.get(label)
        if isinstance(value, dict):
            ready = value.get("supported", value.get("available", True))
            marker = "[green]✓[/]" if ready else "[yellow]![/]"
            console.print(f"{marker} {label.replace('_', ' ').title()}")
            recovery = value.get("recovery") or value.get("warning")
            if recovery:
                console.print(f"  [dim]{recovery}[/dim]")


def _connection_receipt(payload: dict[str, object]) -> Panel:
    """Render a secret-free provider test result."""
    details = ["[green]Connection test passed.[/green]"]
    for key in ("provider", "profile", "mode", "libraries_available", "remaining"):
        if payload.get(key) is not None:
            details.append(f"{key.replace('_', ' ').title()}: {payload[key]}")
    return Panel("\n".join(details), title="Connection receipt", border_style="green")


def _configure_openalex_setup() -> None:
    """Create and test one user-local OpenAlex profile."""
    name = _text("Profile name", "default")
    set_credential("openalex", name, _secret("OpenAlex API key"))
    configure_profile(
        name,
        ConnectionProfile(
            provider="openalex",
            credential_profile=name,
            environment_variable="OPENALEX_API_KEY",
        ),
    )
    console.print(_connection_receipt(test_profile("openalex", name)))


def _configure_semantic_scholar_setup() -> None:
    """Create an optional user-local Semantic Scholar discovery profile."""
    name = _text("Profile name", "default")
    if _yes_no("Store an API key for higher authenticated limits?", False):
        set_credential("semantic_scholar", name, _secret("Semantic Scholar API key"))
    configure_profile(
        name,
        ConnectionProfile(
            provider="semantic_scholar",
            credential_profile=name,
            environment_variable="SEMANTIC_SCHOLAR_API_KEY",
        ),
    )
    console.print(
        "[green]Semantic Scholar profile saved.[/] Public discovery works without a key; "
        "network access occurs only when a literature command is run."
    )


def _configure_hpc_setup() -> None:
    """Create a typed native or OpenSSH Slurm profile outside the project."""
    name = _text("Compute profile name", "default")
    mode = _select(
        "Slurm connection",
        [
            (ComputeMode.NATIVE, "Native · this machine already has Slurm commands"),
            (ComputeMode.SSH, "OpenSSH · use an existing secure host alias"),
        ],
    )
    host = _text("OpenSSH host alias") if mode is ComputeMode.SSH else None
    remote_root = _text("Remote job root", "/shared/smairt-jobs")
    configure_slurm_profile(
        name,
        SlurmProfile(mode=mode, host_alias=host, remote_root=remote_root),
    )
    console.print(
        "[green]Slurm profile saved.[/] SMAIRT stored no password or private key. "
        "Local execution remains the default."
    )


def _configure_zotero_setup() -> None:
    """Create local or Web Zotero access with guided library discovery."""
    name = _text("Profile name", "default")
    mode = _select(
        "Zotero connection",
        [
            (ZoteroMode.LOCAL, "Local Zotero app · no key · read-only"),
            (ZoteroMode.WEB, "Zotero Web library · read-only API key"),
        ],
    )
    if mode is ZoteroMode.LOCAL:
        configure_profile(
            name,
            ConnectionProfile(provider="zotero", credential_profile=name, mode=mode),
        )
    else:
        set_credential("zotero", name, _secret("Zotero read-only API key"))
        provisional = ConnectionProfile(
            provider="zotero",
            credential_profile=name,
            environment_variable="ZOTERO_API_KEY",
            mode=mode,
            library_id="pending",
            library_type=ZoteroLibraryType.USER,
        )
        libraries = discover_zotero_libraries(provisional)
        library_type, library_id = _select(
            "Library",
            [((kind, identifier), label) for kind, identifier, label in libraries],
        )
        configure_profile(
            name,
            ConnectionProfile(
                provider="zotero",
                credential_profile=name,
                environment_variable="ZOTERO_API_KEY",
                mode=mode,
                library_id=library_id,
                library_type=ZoteroLibraryType(library_type),
            ),
        )
    console.print(_connection_receipt(test_profile("zotero", name)))
