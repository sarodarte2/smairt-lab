# See docs/ARCHITECTURE.md for the full tour of how a command flows from here
# down into the shared modules (project.py, units.py, check.py, ...).
"""``smairt`` — the command-line entry point every researcher and harness actually types.

This is the thin top layer: each function below is one ``smairt`` subcommand
(``new``, ``adopt``, ``check``, ``status``, ``connect``, ``unit new``,
``index``). None of them contain real logic — each one just parses its
options (Typer, the library imported below, turns each function's arguments
into CLI flags automatically), calls into the matching module
(:mod:`smairt.project`, :mod:`smairt.units`, :mod:`smairt.check`, etc.) to do
the actual work, and prints the result.

Note for readers: a command function's docstring becomes its ``--help`` text
(Typer reads it directly), so those docstrings are part of SMAIRT's public,
user-facing behavior — unlike everywhere else in this codebase, they are not
free to reword.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Callable, NoReturn

import typer

from smairt import __version__
from smairt import adopt as adopt_module
from smairt import check as check_module
from smairt import connect as connect_module
from smairt import data as data_module
from smairt import index as index_module
from smairt import project as project_module
from smairt import status as status_module
from smairt import units as units_module
from smairt.fsutil import PathExistsError, WriteError
from smairt.project import Harness
from smairt.text import has_usable_characters, slugify

app = typer.Typer(
    no_args_is_help=True,
    invoke_without_command=True,
    help="Create and manage SMAIRT research workspaces.",
)

# Historical marker from earlier development: commands not yet implemented
# used to be listed here so tests could assert they were still stubs. Every
# command is now real, so this stays empty; test_cli.py checks it stays that
# way (a non-empty tuple would mean a command regressed to a stub).
STUB_COMMANDS: tuple[str, ...] = ()


def _version_callback(value: bool) -> None:
    """Print the version and exit immediately, if ``--version`` was passed.

    Typer calls this as soon as it parses ``--version`` (before running any
    command, because the option is ``is_eager=True`` below) — that's why
    ``smairt --version`` works without needing a subcommand.
    """
    if value:
        typer.echo(f"smairt {__version__}")
        raise typer.Exit()


@app.callback()
def smairt(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the SMAIRT version and exit.",
    ),
) -> None:
    """Create and manage SMAIRT research workspaces."""


def _fail(command: str, message: str) -> NoReturn:
    """Print an error to stderr in the "smairt <command>: <message>" shape, then exit 1.

    Every command's error handling goes through this one function so the
    error format is consistent no matter which command failed. ``NoReturn``
    tells mypy this function never returns normally (it always raises) — so
    callers like :func:`_require_project_root` below don't need an `else`.
    """
    typer.echo(f"smairt {command}: {message}", err=True)
    raise typer.Exit(code=1)


def _require_project_root(command: str) -> Path:
    """Find the current SMAIRT project's root folder, or exit with an error.

    Every command except ``new`` needs to already be inside a project (found
    the same way Git finds its repo root — see
    :func:`smairt.project.find_project_root`). Centralizing this one check
    here means each command below is one line shorter and the "not a SMAIRT
    project" message is worded identically everywhere.

    ``hook`` deliberately does not use this helper — see
    :data:`_HOOK_OUTSIDE_PROJECT_MESSAGE`. Also catches
    :class:`smairt.project.ProjectConfigError` (DG-1's fail-fast: a
    ``smairt.yaml`` was found but isn't valid YAML) and turns it into the
    same ``smairt <command>: ...`` shape every other failure here uses,
    rather than letting it propagate as a raw exception.
    """
    try:
        root = project_module.find_project_root(Path.cwd())
    except project_module.ProjectConfigError as error:
        _fail(command, str(error))
    if root is None:
        _fail(
            command, "not a SMAIRT project (no smairt.yaml found in this or any parent directory)."
        )
    return root


_HOOK_OUTSIDE_PROJECT_MESSAGE = (
    "not inside a SMAIRT project (no smairt.yaml found in this or any parent "
    "directory). If a harness ran this hook outside a project, a smairt entry "
    "likely leaked into your global harness config — remove smairt entries "
    "from e.g. ~/.claude/settings.json or ~/.cursor/hooks.json; generated "
    "wiring belongs only inside a project."
)
"""The ``hook`` command's own "not a project" message — deliberately louder than
:func:`_require_project_root`'s generic one.

Every other command that hits this case was typed by a researcher sitting at a
terminal in the wrong directory; the generic message is enough. ``hook`` is
different: it is almost always invoked unattended by a harness's own hook
runner, not by a human, so the most likely real cause is a stale or
accidentally-global harness config (e.g. a smairt entry copied into
``~/.claude/settings.json`` instead of the project-local file ``smairt
connect`` generates) firing this hook in a directory that was never a SMAIRT
project at all. Naming that cause and its fix here saves a confused researcher
a debugging session. This still exits 1 (via :func:`_fail`), never 2 — a
missing project is not a "findings exist, block the action" signal, and exit 2
must stay reserved for that in harnesses where it means "block".
"""


def _prompt_harness(default: Harness = Harness.claude_code) -> Harness:
    """Prompt for a harness as a numbered choice, re-prompting on a bad answer.

    Accepts either the number or the exact name (``2`` or ``codex``) and
    never lets a typo escape as a raw ``ValueError`` traceback — the one real
    defect in the free-text prompt this replaced. Still a plain
    :func:`typer.prompt` underneath, so piped stdin keeps working the same
    way it always has.
    """
    members = list(Harness)
    typer.secho("Harness:", fg=typer.colors.CYAN, bold=True)
    for index, member in enumerate(members, start=1):
        marker = " (default)" if member is default else ""
        typer.echo(f"  {index}. {member.value}{marker}")
    while True:
        answer = typer.prompt("Choice (number or name)", default=default.value).strip()
        if answer.isdigit():
            position = int(answer)
            if 1 <= position <= len(members):
                return members[position - 1]
        else:
            try:
                return Harness(answer)
            except ValueError:
                pass
        typer.echo(f"'{answer}' isn't one of the choices above — try a number or an exact name.")


def _confirm_or_default(prompt: str, *, default: bool) -> bool:
    """Ask a yes/no question with :func:`typer.confirm`, but only at a real terminal.

    A headless caller -- CI, an assistant harness driving `smairt new` (or
    `smairt adopt`) non-interactively, or a `CliRunner` invocation in tests --
    has no tty for `typer.confirm` to read from, and aborting there is worse
    than silently taking the documented default. So this only prompts when
    ``sys.stdin.isatty()``; otherwise it returns ``default`` unasked -- the
    same value `typer.confirm` would have shown as its own default.
    """
    return typer.confirm(prompt, default=default) if sys.stdin.isatty() else default


def _prompt_text_or_default(intro: Callable[[], None], prompt: str, *, default: str) -> str:
    """Ask a free-text question with :func:`typer.prompt`, but only at a real terminal.

    The free-text sibling of :func:`_confirm_or_default`, needed once
    ``--question``/``--expertise`` added two more optional prompts that (unlike
    the yes/no hpc/paper/git ones) take arbitrary text rather than a bool: a
    plain ``typer.prompt(..., default="")`` is NOT gated by ``isatty()`` the
    way ``typer.confirm`` is, so calling one unconditionally would try to read
    a line from stdin even under a headless caller with none to give -- e.g. a
    `CliRunner` test that passes every other identity flag and expects
    ZERO prompts (the "non-interactive contract" the ``smairt-new-project``
    skill explicitly documents and the test suite guards). Skipping the
    ``intro`` callback too, not just the prompt itself, matters just as much:
    the multi-line "here's what a good answer looks like" text these two
    prompts print (see :func:`_prompt_big_question` / :func:`_prompt_expertise`)
    would otherwise show up as unexplained noise in every non-interactive
    ``smairt new``/``smairt adopt`` run and every test's captured output.
    ``intro`` is a thunk (a zero-argument callable) rather than a pre-rendered
    string so it is never even evaluated -- let alone printed -- on the
    skip path.
    """
    if not sys.stdin.isatty():
        return default
    intro()
    return str(typer.prompt(prompt, default=default)).strip()


_BIG_QUESTION_EXAMPLES = (
    "Does denoising recover the true signal in low-SNR live-cell imaging, "
    "or does it invent structure?",
    "Which host factors predict severe outcome in the 2024 cohort, "
    "independent of age?",
)


def _prompt_big_question() -> str:
    """Prompt for the project's "big question" -- ``smairt new --question``'s value.

    Root cause this exists to fix: ``smairt new`` used to collect only filing
    metadata (name/researcher/description/harness/hpc/paper/git) and never
    asked about INTENT -- the actual question the whole project hangs off,
    which is what ``background/question.md`` is FOR. Without this prompt, that
    file ships as an unedited placeholder and the researcher's one-line
    ``description`` leaks into ``STATUS.md``'s ``## Focus`` as if it were the
    science, because description was the only text `smairt new` ever had.

    Deliberately skippable (``default=""``, and the whole prompt is skipped
    outright under a headless caller -- see :func:`_prompt_text_or_default`):
    a researcher genuinely may not have this phrased on day one, and forcing
    a vague placeholder answer into it (rather than the honest, later-
    replaceable placeholder ``smairt new`` already writes) would be worse
    than the gap this closes. See :func:`smairt.project.create_project`'s
    docstring for exactly what changes downstream when this IS answered vs.
    skipped.

    The two example questions printed here are the actual fix for the
    SECOND failure mode this addresses, not just the missing prompt: a
    researcher asked "what's your big question" with no model of the answer
    tends to answer at description-level vagueness ("understanding gene
    expression"), which would make ``question.md`` no more useful than the
    placeholder it replaces. Both examples are deliberately concrete,
    falsifiable, and about ONE dataset/cohort/system, not a field -- modeling
    the granularity a useful answer needs, not just that an answer is wanted.
    """

    def _intro() -> None:
        typer.secho("Big question:", fg=typer.colors.CYAN, bold=True)
        typer.echo(
            "The one question everything under experiments/ answers -- concrete and "
            "falsifiable, about one dataset or system, not a field. Skip if you don't "
            "have it phrased yet."
        )
        for example in _BIG_QUESTION_EXAMPLES:
            typer.echo(f'  e.g. "{example}"')

    return _prompt_text_or_default(_intro, "Big question (Enter to skip)", default="")


_EXPERTISE_EXAMPLES = (
    "computational immunology; wet-lab background, not a programmer",
    "single-cell genomics; comfortable in R, learning Python",
    "materials chemistry; heavy MATLAB user, new to version control",
    "clinical epidemiology; I write SQL, I don't write scripts",
)


def _prompt_expertise() -> str:
    """Prompt for the researcher's own background -- ``--expertise``'s value.

    This is the highest-value prompt this file added, and the reason is a
    specific failure mode a researcher described directly: asked for their
    background, they said they would have written "Computational Biology" --
    and thought that answer was already very detailed. It is a field name,
    and a field name alone tells an assistant nothing about how to talk to
    the person who typed it.

    The examples below all have two halves on purpose, and the prompt text
    says so explicitly, because the second half is the one that actually
    changes assistant behavior: "computational immunology" alone doesn't
    tell an assistant whether to explain what a ``for`` loop is; "wet-lab
    background, not a programmer" does. A field alone (what the researcher
    would have typed unprompted, per the report above) changes nothing about
    HOW an assistant should talk -- only the tooling-comfort half does, which
    is exactly why every example pairs one with the other rather than
    listing field names alone.

    Skippable for the same reason ``--question`` is (see
    :func:`_prompt_big_question`): a good two-half answer takes a moment to
    compose, and a rushed, low-information one (just restating the field) is
    worse than leaving ``expertise:`` absent -- an absent field costs
    nothing (see :func:`smairt.project.render_identity`'s docstring: no key
    is written at all, and it is never a `smairt check` finding), where a
    hollow one would sit in ``smairt.yaml``/``AGENTS.md`` looking authoritative
    while carrying no more information than the field name already did.
    """

    def _intro() -> None:
        typer.secho("Your background:", fg=typer.colors.CYAN, bold=True)
        typer.echo(
            "Your field, plus how much of the computing side you want explained. The "
            "second half matters more than the first:"
        )
        for example in _EXPERTISE_EXAMPLES:
            typer.echo(f"  {example}")

    return _prompt_text_or_default(_intro, "Your background (Enter to skip)", default="")


def _prompt_missing_identity(
    name: str | None,
    researcher: str | None,
    description: str | None,
    harness: Harness | None,
    *,
    question: str | None = None,
    ask_question: bool = False,
    expertise: str | None = None,
) -> tuple[str, str, str, Harness, str, str]:
    """Prompt for whichever of name/researcher/description/harness is still ``None``,
    plus the optional question/expertise prompts.

    Shared by ``new`` and ``adopt`` so the identity prompts — including the
    harness choice — are worded identically no matter which command
    triggered them. ``question``/``expertise`` are always returned as plain
    ``str`` (never ``None``): a caller that never asked (``ask_question=False``,
    ``adopt``'s permanent state) or a researcher who skipped gets back ``""``,
    so every caller can hand the result straight to
    :func:`smairt.project.create_project` /
    :func:`smairt.adopt.adopt_project` without an extra ``or ""`` at each
    call site.

    ``ask_question`` gates the big-question prompt because it is ``new``-only
    (spec: adoption never writes ``background/question.md`` -- see
    :mod:`smairt.adopt`'s module docstring) — ``adopt`` always calls this with
    the default ``False`` and never even passes a CLI flag for it, so the
    prompt genuinely cannot fire from that command. ``expertise`` has no such
    gate because both commands support it identically (see
    :func:`smairt.adopt.adopt_project`'s docstring for why that one applies
    equally to new and adopted work); the parameter here just carries through
    whatever ``--expertise`` (or the interactive answer) already produced,
    same as ``name``/``researcher``/``description`` above it.

    Ordering: question (when asked) comes right after description -- the
    identity questions proper -- and before harness/expertise, since it's the
    most consequential thing a researcher decides in this flow and shouldn't
    be buried after the harness picker. Expertise comes last, right before
    return, since it's about the researcher rather than the project and reads
    naturally as a closing question.
    """
    if name is None:
        name = typer.prompt("Project name")
    if researcher is None:
        researcher = typer.prompt("Researcher")
    if description is None:
        description = typer.prompt("One-line description")
    if ask_question and question is None:
        question = _prompt_big_question()
    if harness is None:
        harness = _prompt_harness()
    if expertise is None:
        expertise = _prompt_expertise()
    return name, researcher, description, harness, question or "", expertise or ""


_HARNESS_LAUNCH_COMMAND: dict[Harness, str] = {
    Harness.claude_code: "claude",
    Harness.codex: "codex",
    Harness.opencode: "opencode",
    Harness.gemini_cli: "gemini",
    Harness.cursor: "cursor",
    Harness.pi: "pi",
}
"""How each harness is actually typed at a terminal to start a session.

Deliberately not just ``Harness.value`` (``"claude-code"``, ``"gemini-cli"``)
-- those are ``smairt``'s own identifiers for ``--harness``/``smairt.yaml``,
not the real command a researcher runs. Used only by :func:`_print_next_steps`
below, where naming the actual harness (not a generic "start your assistant")
is the entire point -- see that function's docstring.
"""


def _print_next_steps(root: Path, harness: Harness) -> None:
    """Print the closing "what do I do now" block after ``smairt new`` finishes.

    Root cause this exists to fix: ``smairt new`` used to end at "Created
    <root>" (plus the connect/git lines) and stop -- a researcher described
    their own next move at that point as "my best guess was jump into the
    folder", i.e. they had no idea what to do after the folder existed. The
    fix is not a longer explanation; it's literally handing them the three
    commands/words that get them into a working session, ending with the
    exact sentence to say, because "open your assistant and describe your
    problem" is a much higher-friction ask than "type this."

    Names the actual harness the researcher chose (``claude``, ``codex``,
    ``cursor``, ``opencode``, ``gemini``, ``pi`` -- see
    :data:`_HARNESS_LAUNCH_COMMAND`), never a generic "start your assistant":
    a researcher who just answered the harness prompt should not have to
    translate a generic instruction back into the tool they actually have
    open. When ``harness`` is :data:`Harness.none`, there is no assistant to
    talk to, so the block points at the CLI path instead
    (``smairt unit new question``) rather than printing a launch command and
    a sentence to say to nobody.

    Prints ``cd <folder>`` using a path relative to the current working
    directory when ``root`` is under it (the common case -- a researcher who
    just ran ``smairt new`` from the parent directory), falling back to the
    absolute path when it isn't (e.g. ``--path`` pointed somewhere else
    entirely) -- ``Path.relative_to`` raises ``ValueError`` in that case,
    which is the signal to use the full path instead of a nonsensical
    ``../../`` chain.

    HARD CONSTRAINT, not a style choice: this block says nothing about Git,
    ever, regardless of whether ``smairt new --git`` ran. The researcher who
    stays local made that choice on purpose ("it should be an option, not
    ideal but an option," in their own words) -- the existing git-outcome
    line above this block (in :func:`new`) already tells them what happened
    if they asked for it; re-litigating or nagging about it in the one block
    whose entire job is "get to a working session" would undercut a decision
    that was never this block's to second-guess.
    """
    try:
        cd_target = root.relative_to(Path.cwd())
    except ValueError:
        cd_target = root
    typer.echo("")
    typer.echo("Next:")
    typer.echo(f"  cd {cd_target}")
    if harness is Harness.none:
        typer.echo("  smairt unit new question    # create your first question unit")
    else:
        typer.echo(f"  {_HARNESS_LAUNCH_COMMAND[harness]}            # start your assistant here")
        typer.echo('  Then say: "Help me start my first question."')


@app.command()
def new(
    name: str | None = typer.Option(None, "--name", help="Project name."),
    researcher: str | None = typer.Option(None, "--researcher", help="Researcher name."),
    description: str | None = typer.Option(
        None, "--description", help="One-line project description."
    ),
    question: str | None = typer.Option(
        None,
        "--question",
        help="The project's big question: becomes background/question.md and STATUS.md's Focus.",
    ),
    expertise: str | None = typer.Option(
        None,
        "--expertise",
        help="Your field plus how much of the computing side you want explained.",
    ),
    path: Path | None = typer.Option(
        None, "--path", help="Parent directory for the new project (default: current directory)."
    ),
    harness: Harness | None = typer.Option(
        None, "--harness", help="Assistant harness to record in smairt.yaml."
    ),
    hpc: bool | None = typer.Option(
        None, "--hpc/--no-hpc", help="Also generate hpc/ with a commented SLURM template."
    ),
    paper: bool | None = typer.Option(
        None, "--paper/--no-paper", help="Note paper support under STATUS.md open questions."
    ),
    git: bool | None = typer.Option(
        None,
        "--git/--no-git",
        help="Initialize a Git repository and stage the scaffold (never commits).",
    ),
) -> None:
    """Create a new SMAIRT project: the ten-item day-one scaffold."""
    name, researcher, description, harness, question, expertise = _prompt_missing_identity(
        name,
        researcher,
        description,
        harness,
        question=question,
        ask_question=True,
        expertise=expertise,
    )
    if hpc is None:
        hpc = _confirm_or_default("Expect to run on HPC/SLURM?", default=False)
    if paper is None:
        paper = _confirm_or_default("Expect this project to support a paper?", default=False)
    if git is None:
        git = _confirm_or_default("Initialize a Git repository?", default=True)

    if not has_usable_characters(name):
        typer.echo(
            "Warning: --name has no letters or digits smairt can use for a folder "
            "name; using 'project' instead of a name derived from it.",
            err=True,
        )
    parent = path or Path.cwd()
    # DG-3: check for nesting BEFORE creating anything, so the warning below
    # is about an OUTER project already there, never the one about to be
    # created. Existence-only (find_enclosing_project, not find_project_root)
    # on purpose: a broken smairt.yaml in that outer, unrelated project is
    # not a reason to refuse creating this new one -- see
    # smairt.project.find_enclosing_project's docstring.
    enclosing = project_module.find_enclosing_project(parent)
    root = parent / slugify(name, fallback="project")
    try:
        project_module.create_project(
            root,
            name=name,
            researcher=researcher,
            description=description,
            harness=harness,
            hpc=hpc,
            paper=paper,
            question=question,
            expertise=expertise,
            git=git,
        )
    except (PathExistsError, WriteError, ValueError) as error:
        _fail("new", str(error))

    typer.secho(f"Created {root}", fg=typer.colors.GREEN, bold=True)
    if enclosing is not None:
        # Still created (per DG-1's decision) -- this only names the
        # situation. Voice matches init_git's own nesting message below
        # ("this project sits inside an existing Git repository, so Git was
        # left alone..."): plain language, says what happened and which
        # project wins for commands run inside this one.
        typer.echo(
            f"Warning: this project sits inside an existing SMAIRT project "
            f"({enclosing / 'smairt.yaml'}), so smairt commands run from inside {root} "
            "will read ITS OWN smairt.yaml, not the outer project's -- the outer "
            "project will only see this folder as unfamiliar structure (flagged as "
            "SMAIRT006 by its own `smairt check`) unless the nesting is intentional.",
            err=True,
        )
    if harness is not Harness.none:
        result = connect_module.connect(root, harness, strict=False)
        _report_connect(result)

    # Git init/add runs LAST, after the harness wiring above, so everything
    # `smairt new` generates -- smairt.yaml, AGENTS.md, and the harness's own
    # hook config -- gets staged together, not just the day-one scaffold. The
    # git/no-git DECISION itself was already made above, before create_project
    # ran, so create_project could record it (settings.git: false on an
    # opt-out -- see smairt.project.render_identity) regardless of when the
    # actual `git init` call happens.
    if git:
        git_result = project_module.init_git(root)
        if git_result.outcome == "initialized":
            typer.echo("Initialized a Git repository and staged the scaffold (nothing committed).")
        elif git_result.outcome == "skipped":
            # Not a warning -- e.g. `root` is nested inside a Git repo that
            # starts above it, so backing off (rather than nesting a second
            # repo inside the first) IS the correct outcome. See
            # smairt.project.init_git's docstring.
            typer.echo(git_result.message)
        else:
            typer.echo(f"Warning: {git_result.message}", err=True)

    _print_next_steps(root, harness)


@app.command()
def adopt(
    name: str | None = typer.Option(None, "--name", help="Project name."),
    researcher: str | None = typer.Option(None, "--researcher", help="Researcher name."),
    description: str | None = typer.Option(
        None, "--description", help="One-line project description."
    ),
    expertise: str | None = typer.Option(
        None,
        "--expertise",
        help="Your field plus how much of the computing side you want explained.",
    ),
    path: Path | None = typer.Option(
        None, "--path", help="Directory to adopt (default: current directory)."
    ),
    harness: Harness | None = typer.Option(
        None, "--harness", help="Assistant harness to record in smairt.yaml."
    ),
) -> None:
    """Adopt a pre-existing directory: lay the contract files around it, move nothing."""
    name, researcher, description, harness, _question, expertise = _prompt_missing_identity(
        name, researcher, description, harness, expertise=expertise
    )

    root = path or Path.cwd()
    try:
        result = adopt_module.adopt_project(
            root,
            name=name,
            researcher=researcher,
            description=description,
            harness=harness,
            expertise=expertise,
        )
    except (adopt_module.NotAdoptableError, WriteError, ValueError) as error:
        _fail("adopt", str(error))

    typer.echo(f"Adopted {root}")
    typer.echo(f"Known folders: {', '.join(result.known_folders) or '(none)'}")
    for written in result.written:
        typer.echo(f"Wrote {written}")
    for unchanged in result.skipped:
        typer.echo(f"Unchanged {unchanged}")
    for warning in result.warned:
        typer.echo(f"Warning: {warning}", err=True)
    if result.connect_result is not None:
        _report_connect(result.connect_result)


@app.command()
def check(
    json_output: bool = typer.Option(
        False, "--json", help="Emit machine-readable JSON instead of human-readable text."
    ),
) -> None:
    """Check a project's state contract: frontmatter, evidence, drift, and more."""
    root = _require_project_root("check")
    report = check_module.run_checks(root)
    if json_output:
        typer.echo(json.dumps(check_module.to_json(report), indent=2))
    else:
        typer.echo(check_module.render_human(report))
    raise typer.Exit(code=report.exit_code)


@app.command()
def hook(
    mode: str = typer.Argument(
        ...,
        help=(
            "'report' prints findings and always exits 0; "
            "'brief' prints `smairt status`'s human view and always exits 0; "
            "'gate' exits 2 while findings exist (the block code harness hooks understand)."
        ),
    ),
) -> None:
    """Run `smairt check`/`smairt status` speaking a harness hook's exit-code protocol.

    Generated hook configs (see ``smairt connect``) call this instead of
    ``smairt check``/``smairt status`` directly, because the raw commands
    either exit 1 on findings (`check`) or were never designed to run
    unattended inside a hook at all (`status`), and hook protocols give exit
    codes different meanings: Claude Code, Codex, and Cursor all treat exit 2
    as "block this action and feed stderr back to the agent", while exit 1 is
    a plain non-blocking error. ``gate`` speaks that blocking dialect;
    ``report`` and ``brief`` both speak the OTHER dialect -- "surface
    information, never wedge the harness in a failure loop" -- for the two
    ends of a session: ``report`` at session end (this project's `smairt
    check` findings), ``brief`` at session START (this project's
    orientation, via :func:`smairt.status.build_status_report` --
    ``smairt hook brief`` exists specifically so a fresh assistant session
    orients itself the moment it opens, without the researcher having to
    think to ask for `smairt status`). See ``smairt connect claude-code``'s
    generated ``.claude/settings.json`` for where ``SessionStart``/``Stop``
    wire each of these up.
    """
    if mode not in ("report", "gate", "brief"):
        _fail("hook", f"unknown mode {mode!r}. Choices: report, gate, brief.")
    try:
        root = project_module.find_project_root(Path.cwd())
    except project_module.ProjectConfigError as error:
        # Still exits 1, never 2 -- see _HOOK_OUTSIDE_PROJECT_MESSAGE's own
        # docstring for why exit 2 must stay reserved for "findings exist,
        # block the action" and never mean "smairt itself couldn't run".
        _fail("hook", str(error))
    if root is None:
        _fail("hook", _HOOK_OUTSIDE_PROJECT_MESSAGE)

    if mode == "brief":
        # A separate branch, not folded into the report/gate try/except below:
        # `brief` calls a different function (`build_status_report`, not
        # `run_checks`) with a different renderer and a different crash
        # message, but makes the exact same "must never wedge the session"
        # promise `report` makes below, for the identical reason -- that
        # promise cannot hold only while smairt itself is bug-free.
        try:
            status_report = status_module.build_status_report(root)
        except Exception as error:  # noqa: BLE001 - see above; a hook must never crash a session.
            typer.echo(
                f"smairt hook: `smairt status` failed unexpectedly: {error}. "
                "This is a smairt bug, not a problem with your project; run `smairt "
                "status` directly to see it in full.",
                err=True,
            )
            raise typer.Exit(code=0) from error
        output = status_module.render_human(status_report)
        # A brand-new project -- no stages, no open questions, no closed
        # questions either -- is exactly the case that used to strand a
        # researcher: `smairt new` created the scaffold and stopped, and a
        # fresh assistant session had no signal that the very first move is
        # creating a unit. One sentence closes that gap right where the
        # assistant will actually see it, instead of relying on AGENTS.md
        # being read carefully enough to notice the gap on its own.
        has_units = bool(
            status_report.spine or status_report.live_questions or status_report.recently_closed
        )
        if not has_units:
            output += (
                "\n\nNo units yet -- create the first one with `smairt unit new stage|question`."
            )
        typer.echo(output)
        raise typer.Exit(code=0)

    try:
        report = check_module.run_checks(root)
    except Exception as error:  # noqa: BLE001 - see below; a hook must never crash a session.
        # `report`'s "always exits 0" and `gate`'s "2 means findings exist" are
        # promises the README and every generated hook config rely on, so they
        # cannot hold only while smairt is bug-free. An unexpected failure here
        # is a smairt defect, not a finding about the researcher's project, and
        # neither harness protocol has a code that says so -- so `report` keeps
        # its promise and exits 0, and `gate` exits 1: a plain non-blocking
        # error. Never 2, which must keep meaning "findings exist, block", for
        # the same reason _HOOK_OUTSIDE_PROJECT_MESSAGE exits 1 rather than 2.
        # Blocking every edit in the session because smairt itself broke would
        # wedge the researcher out of their own work with no way to proceed.
        typer.echo(
            f"smairt hook: `smairt check` failed unexpectedly: {error}. "
            "This is a smairt bug, not a problem with your project; run `smairt "
            "check` directly to see it in full.",
            err=True,
        )
        raise typer.Exit(code=0 if mode == "report" else 1) from error
    if mode == "report":
        typer.echo(check_module.render_human(report))
        raise typer.Exit(code=0)
    if report.exit_code == 0:
        raise typer.Exit(code=0)
    # Findings exist: block. Stderr is what blocking harnesses relay to the agent.
    typer.echo(check_module.render_human(report), err=True)
    raise typer.Exit(code=2)


@app.command()
def status(
    json_output: bool = typer.Option(
        False, "--json", help="Emit machine-readable JSON instead of human-readable text."
    ),
) -> None:
    """Show project orientation: focus, spine, live/closed questions, and warnings."""
    root = _require_project_root("status")
    report = status_module.build_status_report(root)
    if json_output:
        typer.echo(json.dumps(status_module.to_json(report), indent=2))
    else:
        typer.echo(status_module.render_human(report))


def _report_connect(result: connect_module.ConnectResult) -> None:
    """Print a :class:`~smairt.connect.ConnectResult` the same way after every call.

    Shared by the ``new`` command (which connects a harness automatically),
    ``adopt``, and ``connect`` itself, so "Wrote X" / "Unchanged X" /
    "Warning: ..." always reads identically no matter which command
    triggered the harness wiring.
    """
    for path in result.written:
        typer.echo(f"Wrote {path}")
    for path in result.skipped:
        typer.echo(f"Unchanged {path}")
    for warning in result.warned:
        typer.echo(f"Warning: {warning}", err=True)
    if not (result.written or result.skipped or result.warned):
        typer.echo("Nothing to do.")


@app.command()
def connect(
    harness: str | None = typer.Argument(
        None,
        help=(
            "Harness to wire up (claude-code, codex, opencode, gemini-cli, cursor, pi), "
            "or 'ci' for the GitHub Actions template."
        ),
    ),
    ci: bool = typer.Option(
        False, "--ci", help="Write the GitHub Actions CI template instead of harness wiring."
    ),
) -> None:
    """Wire an assistant harness's hooks to `smairt check` (bridge file + hook config)."""
    root = _require_project_root("connect")

    if ci or harness == "ci":
        _report_connect(connect_module.connect_ci(root))
        return

    if harness is None:
        _fail(
            "connect",
            "a harness is required (claude-code, codex, opencode, gemini-cli, cursor, pi), "
            "or pass --ci.",
        )

    try:
        harness_value = Harness(harness)
    except ValueError:
        choices = ", ".join(member.value for member in Harness if member is not Harness.none)
        _fail("connect", f"unknown harness {harness!r}. Choices: {choices}, ci.")

    if harness_value is Harness.none:
        _fail("connect", "harness 'none' has no wiring to install.")

    strict = connect_module.read_strict_hooks(root)
    _report_connect(connect_module.connect(root, harness_value, strict=strict))


unit_app = typer.Typer(no_args_is_help=True, help="Create units of research.")
app.add_typer(unit_app, name="unit")


@unit_app.command("new")
def unit_new(
    kind: units_module.UnitKind = typer.Argument(..., help="'stage' or 'question'."),
    title: str = typer.Option(..., "--title", help="Unit title."),
    hypothesis: str | None = typer.Option(
        None, "--hypothesis", help="The probe's hypothesis (question units only)."
    ),
    from_unit: str | None = typer.Option(
        None,
        "--from",
        help=(
            "Origin unit's folder name (question units only): this question was "
            "prompted by that unit's result. Validated to exist at creation."
        ),
    ),
    receipt: bool = typer.Option(
        False, "--receipt", help="Record this unit as a receipt for an outside tool."
    ),
    tool: str | None = typer.Option(None, "--tool", help="Outside tool name (with --receipt)."),
    tool_version: str | None = typer.Option(
        None, "--tool-version", help="Outside tool version (with --receipt)."
    ),
    command: str | None = typer.Option(
        None, "--command", help="Exact command that was run (with --receipt)."
    ),
    repo: str | None = typer.Option(
        None, "--repo", help="Tool repo URL and commit, if any (with --receipt)."
    ),
    ref: list[str] = typer.Option(
        [],
        "--ref",
        help=(
            "Existing path this unit references, relative to the project root "
            "(repeatable). Creates a thin, README-only reference unit — case 3, "
            "how pre-existing work gets a unit without moving it. Validated to "
            "exist at creation."
        ),
    ),
) -> None:
    """Create a stage or question unit under experiments/. The numbering/dating authority."""
    root = _require_project_root("unit new")
    ref_paths = ref or None
    if not has_usable_characters(title):
        fallback = "stage" if kind is units_module.UnitKind.stage else "question"
        typer.echo(
            f"Warning: --title has no letters or digits smairt can use for a folder "
            f"name; using '{fallback}' instead of a name derived from it.",
            err=True,
        )
    try:
        if kind is units_module.UnitKind.stage:
            unit_dir = units_module.create_stage(
                root,
                title,
                receipt=receipt,
                tool=tool,
                tool_version=tool_version,
                command=command,
                repo=repo,
                ref_paths=ref_paths,
            )
        else:
            unit_dir = units_module.create_question(
                root,
                title,
                hypothesis=hypothesis,
                prompted_by=from_unit,
                receipt=receipt,
                tool=tool,
                tool_version=tool_version,
                command=command,
                repo=repo,
                ref_paths=ref_paths,
            )
    except (PathExistsError, WriteError, ValueError) as error:
        _fail("unit new", str(error))

    typer.echo(f"Created {unit_dir.relative_to(root)}")


data_app = typer.Typer(no_args_is_help=True, help="Record where each dataset physically lives.")
app.add_typer(data_app, name="data")


def _parse_hpc_location(value: str, note: str | None) -> data_module.Location:
    """Parse a ``--hpc HOST:PATH`` flag into a :class:`~smairt.data.Location`.

    Fails cleanly (a plain ``ValueError``, not an unhandled ``IndexError``
    from a bad ``.split()``) when ``value`` has no ``:`` separator at all.

    Rejected up front, before the HOST:PATH split: a value containing ``://``
    (``https://example.com/data``, ...). Splitting a URL like that on the
    first ``:`` "succeeds" by the letter of the HOST:PATH rule (both halves
    come out non-empty), but silently produces a nonsense host (``host:
    "https"``) — exactly what a researcher who meant ``--url`` and typed
    ``--hpc`` out of habit would produce, with nothing in the tool ever
    telling them. A real HOST:PATH pair never legitimately contains ``://``.
    """
    if "://" in value:
        raise ValueError(f"--hpc expects HOST:PATH, not a URL (got {value!r}); did you mean --url?")
    if ":" not in value:
        raise ValueError(f"--hpc expects HOST:PATH (got {value!r}, with no ':')")
    host, path = value.split(":", 1)
    if not host.strip() or not path.strip():
        raise ValueError(f"--hpc expects HOST:PATH, both non-empty (got {value!r})")
    return data_module.Location(kind="hpc", host=host, path=path, note=note)


def _collect_new_locations(
    hpc: list[str], url: list[str], local: list[str], note: str | None
) -> list[data_module.Location]:
    """Turn ``data new``'s repeatable location flags into a list of :class:`~smairt.data.Location`.

    ``--note`` is not repeatable, so if it is given alongside more than one
    location flag it is applied to every location created in this one call
    -- a deliberate simplification for the common case (one dataset, one
    note about how it was obtained), not per-location notes.
    """
    locations: list[data_module.Location] = []
    for value in hpc:
        locations.append(_parse_hpc_location(value, note))
    for value in url:
        locations.append(data_module.Location(kind="url", path=value, note=note))
    for value in local:
        locations.append(data_module.Location(kind="local", path=value, note=note))
    return locations


@data_app.command("new")
def data_new(
    name: str = typer.Argument(..., help="Dataset name; slugified into data/<slug>/."),
    hpc: list[str] = typer.Option([], "--hpc", help="An HPC location, as HOST:PATH (repeatable)."),
    url: list[str] = typer.Option([], "--url", help="A download-source URL (repeatable)."),
    local: list[str] = typer.Option(
        [], "--local", help="An additional local path, beyond the dataset folder (repeatable)."
    ),
    note: str | None = typer.Option(
        None, "--note", help="Note applied to every location passed above."
    ),
) -> None:
    """Create data/<slug>/README.md, recording where this dataset's bytes live."""
    root = _require_project_root("data new")
    if not has_usable_characters(name):
        typer.echo(
            "Warning: dataset name has no letters or digits smairt can use for a "
            "folder name; using 'dataset' instead of a name derived from it.",
            err=True,
        )
    try:
        locations = _collect_new_locations(hpc, url, local, note)
        dataset_dir = data_module.create_dataset(root, name, locations=locations)
    except (PathExistsError, WriteError, ValueError) as error:
        _fail("data new", str(error))

    typer.echo(f"Created {dataset_dir.relative_to(root)}")


@data_app.command("locate")
def data_locate(
    name: str = typer.Argument(..., help="Dataset name (as passed to `smairt data new`)."),
    hpc: str | None = typer.Option(None, "--hpc", help="An HPC location, as HOST:PATH."),
    url: str | None = typer.Option(None, "--url", help="A download-source URL."),
    local: str | None = typer.Option(None, "--local", help="A local path."),
    note: str | None = typer.Option(None, "--note", help="Optional note for this location."),
) -> None:
    """Add one location to an existing dataset's README frontmatter."""
    root = _require_project_root("data locate")
    given = [value for value in (hpc, url, local) if value is not None]
    if len(given) != 1:
        _fail("data locate", "exactly one of --hpc, --url, --local is required.")

    try:
        if hpc is not None:
            location = _parse_hpc_location(hpc, note)
        elif url is not None:
            location = data_module.Location(kind="url", path=url, note=note)
        else:
            assert local is not None
            location = data_module.Location(kind="local", path=local, note=note)
        dataset_dir = data_module.add_location(root, name, location)
    except ValueError as error:
        _fail("data locate", str(error))

    typer.echo(f"Updated {dataset_dir.relative_to(root)}/README.md")


@data_app.command("list")
def data_list(
    json_output: bool = typer.Option(
        False, "--json", help="Emit machine-readable JSON instead of human-readable text."
    ),
) -> None:
    """List every dataset under data/ and every location recorded for it."""
    root = _require_project_root("data list")
    report = data_module.list_locations(root)
    if json_output:
        typer.echo(json.dumps(data_module.to_json(report), indent=2))
    else:
        typer.echo(data_module.render_human(report))


@app.command()
def index() -> None:
    """Regenerate results/INDEX.md from every unit's frontmatter header."""
    root = _require_project_root("index")
    path = index_module.write_index(root)
    typer.echo(f"Updated {path.relative_to(root)}")


def main() -> None:
    """The actual entry point installed as the ``smairt`` console script.

    Just hands off to Typer's ``app()``, which parses ``sys.argv`` and
    dispatches to whichever ``@app.command()`` function matches.
    """
    app()


if __name__ == "__main__":
    main()
