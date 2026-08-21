"""``smairt new`` — creates a brand-new project's "day-one scaffold" from scratch.

This is the module a researcher's first command runs through. It renders the
ten starting files/folders a fresh SMAIRT project needs (``smairt.yaml``,
``STATUS.md``, ``AGENTS.md``, ``.gitignore``, ``background/``, ``data/``,
``scripts/``, ``experiments/``, ``results/``, and optionally ``hpc/``) and
writes them once via :func:`smairt.fsutil.write_once` — so running ``smairt
new`` a second time against the same folder is refused rather than silently
overwriting anything.

Most of this file's length is the literal *text* of the generated files
(the big triple-quoted string constants near the bottom, like
``_AGENTS_BODY`` and ``_GITIGNORE``) — the actual logic is short. Two of
its rendering functions are reused elsewhere because the content must be
byte-identical everywhere it appears: :func:`render_identity` and
:func:`render_status` are also called by :mod:`smairt.adopt` (adopting a
pre-existing project uses the same ``smairt.yaml``/``STATUS.md`` shape, just
with different starting values), and :func:`render_agents_md` is the single
place ``AGENTS.md`` is generated for both ``smairt new`` and ``smairt adopt``.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Literal, Mapping, Sequence

import yaml

from smairt import __version__, frontmatter, index
from smairt.fsutil import write_once
from smairt.models import Researcher

SCHEMA_VERSION = 2


class Harness(str, Enum):
    """Assistant harnesses SMAIRT recognizes (Part I, foundation 8: parity, no favorites)."""

    claude_code = "claude-code"
    codex = "codex"
    opencode = "opencode"
    gemini_cli = "gemini-cli"
    cursor = "cursor"
    pi = "pi"
    none = "none"


class ProjectConfigError(RuntimeError):
    """Raised by :func:`find_project_root` when the nearest ``smairt.yaml`` exists
    but is not valid YAML.

    This is DG-1's "fail fast" half (see :mod:`smairt.check`'s "Judgment
    calls" section for the full policy): every command resolves its project
    root through :func:`find_project_root`, so raising here — rather than
    silently walking past a broken config or returning it as if it were
    fine — means every command gives the researcher the identical, repair-
    focused message at the identical point, instead of each command
    discovering the breakage its own way (or not at all) several calls
    later. A file that PARSES but is missing or has the wrong fields is
    deliberately NOT this function's problem — that is rule SMAIRT011,
    checked once the project root is already known to be usable.
    """


def _find_config_upward(start: Path) -> Path | None:
    """The nearest ``smairt.yaml`` at or above ``start``, by existence only.

    Shared by :func:`find_project_root` (which additionally validates the
    result parses) and :func:`find_enclosing_project` (DG-3's nesting check
    for ``smairt new``, which deliberately does NOT validate — a broken
    config in some UNRELATED outer project is not a reason to refuse
    creating a new one, only a reason to note the nesting).
    """
    current = start.resolve()
    for candidate in (current, *current.parents):
        config = candidate / "smairt.yaml"
        if config.is_file():
            return config
    return None


def find_project_root(start: Path) -> Path | None:
    """Walk upward from ``start`` looking for the nearest ``smairt.yaml``.

    This is how every command (``check``, ``status``, ``unit new``, ...)
    figures out "which project am I in" — the same way Git finds the
    repository root by looking for ``.git``. A researcher can run
    ``smairt check`` from any subfolder of their project, not just the top.
    Returns ``None`` if no ``smairt.yaml`` is found before reaching the
    filesystem root (i.e. we're not inside a SMAIRT project at all).

    Raises :class:`ProjectConfigError` if a ``smairt.yaml`` IS found but is
    not valid YAML (DG-1's fail-fast half) — every caller of this function
    is expected to let that propagate up to a `smairt <command>: ...`
    error, not swallow it, so the researcher hears about a broken identity
    file immediately rather than getting a confusing, unrelated failure
    three calls later.
    """
    config = _find_config_upward(start)
    if config is None:
        return None
    try:
        yaml.safe_load(config.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise ProjectConfigError(
            f"{config} is not valid YAML ({_yaml_problem_summary(error)}).\n\n"
            "A correct smairt.yaml looks like this:\n\n" + example_smairt_yaml()
        ) from error
    return config.parent


def find_enclosing_project(start: Path) -> Path | None:
    """The nearest EXISTING SMAIRT project's root at or above ``start``, if any.

    Used only by ``smairt new``'s nesting warning (DG-3): it needs to know
    "is there already a project here", not whether that OTHER project's
    ``smairt.yaml`` happens to be valid -- an outer project's broken config
    is that project's own problem (it will get its own fail-fast the next
    time a command is run inside IT), not a reason to block creating a new,
    unrelated project nested under it. This is why it goes through
    :func:`_find_config_upward` directly rather than :func:`find_project_root`,
    which would raise on exactly that case.
    """
    config = _find_config_upward(start)
    return config.parent if config is not None else None


def _yaml_problem_summary(error: yaml.YAMLError) -> str:
    """A short, human-readable "what's wrong and where" from a PyYAML exception.

    Never the raw ``str(error)`` -- that text says ``in "<unicode string>"``
    (PyYAML has no idea it was reading a file), which reads as an internal
    detail to a researcher who has never seen a YAML error before, and often
    also repeats the problem twice (once for context, once for the failure
    itself). Prefers ``context_mark`` over ``problem_mark`` when both are
    present: for an unterminated quote or an unclosed ``[...]`` list,
    ``problem_mark`` points at the END of the file (where PyYAML gave up),
    while ``context_mark`` points at the line the broken construct actually
    STARTS on -- the line a researcher needs to look at to fix it.
    """
    if not isinstance(error, yaml.MarkedYAMLError):
        return str(error).splitlines()[0]
    problem = error.problem or str(error).splitlines()[0]
    mark = error.context_mark or error.problem_mark
    if mark is not None:
        return f"{problem}, line {mark.line + 1}"
    return problem


@dataclass(frozen=True)
class ProjectConfig:
    """The result of trying to read ``smairt.yaml`` as a usable mapping.

    ``data`` is ``None`` whenever the file can't be used as a mapping at all
    -- missing, not valid YAML, empty, or parsed to something other than a
    YAML mapping (a list, a bare string, ...) -- with ``problem`` naming why
    in each case. Every reader of ``smairt.yaml`` elsewhere in this codebase
    (:mod:`smairt.check`'s rule SMAIRT011 and its adoption-folders reader,
    :mod:`smairt.connect`'s ``strict_hooks``/``harnesses`` readers) goes
    through :func:`read_project_config` rather than calling
    ``yaml.safe_load`` itself, so there is exactly one place that decides
    what counts as "unreadable" and how to describe why. See
    :mod:`smairt.check`'s "Judgment calls" section for the degrade policy
    built on top of this (DG-1).
    """

    data: dict[str, object] | None
    problem: str | None


def read_project_config(project_root: Path) -> ProjectConfig:
    """Read and parse ``project_root / smairt.yaml`` as a mapping.

    Defense in depth, not the primary guard: a YAML SYNTAX error (the kind
    ``yaml.safe_load`` itself raises on) is already caught earlier, and much
    more loudly, by :func:`find_project_root`'s fail-fast -- every `smairt`
    command already refuses to run at all once it can't resolve a project
    whose ``smairt.yaml`` doesn't parse, so by the time this function runs
    inside a real command, ``project_root`` was already proven to have a
    parseable config moments earlier on the same read. This function still
    catches ``yaml.YAMLError`` itself (rather than assuming that can't
    happen) so it never raises on a caller that reaches it without going
    through :func:`find_project_root` first -- a test, or a future direct
    library caller.
    """
    path = project_root / "smairt.yaml"
    if not path.is_file():
        return ProjectConfig(None, "smairt.yaml is missing")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        return ProjectConfig(
            None, f"smairt.yaml is not valid YAML ({_yaml_problem_summary(error)})"
        )
    if raw is None:
        return ProjectConfig(None, "smairt.yaml is empty")
    if not isinstance(raw, dict):
        return ProjectConfig(
            None,
            "smairt.yaml must be a YAML mapping (key: value pairs), not a list or a single value",
        )
    return ProjectConfig(raw, None)


def example_smairt_yaml() -> str:
    """A representative, correct ``smairt.yaml`` an error message can print verbatim.

    Built by calling :func:`render_identity` itself with plausible placeholder
    values, rather than a separately hand-maintained string constant -- so
    this can never drift out of sync with the schema ``render_identity``
    actually writes the way an independent example string could. DG-1's hard
    requirement is that a researcher can repair a broken ``smairt.yaml`` "by
    eye, with no docs lookup" -- this is what makes that possible: every
    fail-fast and SMAIRT011 message ends with this, so the correct shape is
    always one scroll away from the broken one.
    """
    return render_identity(
        "My Project",
        "A. Researcher",
        "One-line description of what this project is trying to answer.",
        Harness.claude_code,
        date(2026, 1, 1),
        __version__,
    )


def create_project(
    root: Path,
    *,
    name: str,
    researcher: str,
    description: str,
    harness: Harness = Harness.claude_code,
    hpc: bool = False,
    paper: bool = False,
    question: str | None = None,
    expertise: str | None = None,
    git: bool = True,
    created: date | None = None,
    scaffold_version: str | None = None,
) -> Path:
    """Render the ten-item day-one scaffold (spec Part II) at ``root``.

    Every file is written once via :func:`smairt.fsutil.write_once`, so re-running
    this against an existing project errors instead of clobbering researcher edits.

    ``question`` and ``expertise`` are both optional and both blank-string-means-
    absent (``cli.py``'s prompts hand back ``""`` on a skip, never ``None``, so
    this treats an empty/whitespace-only string identically to ``None`` rather
    than making every caller remember to normalize it first):

    * ``question`` is the researcher's one-line "big question" -- the thing the
      whole project hangs off. When given, it becomes BOTH
      ``background/question.md``'s body and ``STATUS.md``'s ``## Focus`` (see
      :func:`_render_question_md` and :func:`render_status`'s ``focus=``); when
      absent, both fall back to the exact placeholder/description behavior this
      function always had, so a researcher who skips the prompt (the common,
      explicitly-supported case -- day one is often too early to have this
      phrased) sees zero behavior change. ``description`` is never touched
      either way; it stays the short filing label in ``smairt.yaml`` and
      ``AGENTS.md``'s title line, exactly as before this field existed.
    * ``expertise`` is the researcher's own account of their field plus how much
      of the computing side they want explained -- folded into ``smairt.yaml``
      (:func:`render_identity`) and ``AGENTS.md`` (:func:`render_agents_md`) so
      every harness reading the contract can calibrate jargon accordingly. When
      absent, neither file gains anything: no ``expertise:`` key, no extra
      ``AGENTS.md`` section -- see those two functions' own docstrings for why
      an absent key is not the same as an empty one.

    ``git`` records the researcher's own git/no-git choice into
    ``smairt.yaml``'s ``settings.git`` (see :func:`render_identity`) so
    :mod:`smairt.check`'s SMAIRT101 advisory can tell a deliberate opt-out
    from an accident later, once the project genuinely has no ``.git`` to
    inspect. This function does not act on the choice itself -- running (or
    skipping) ``git init`` is :func:`init_git`'s job, called separately by
    ``cli.py``'s ``new`` command AFTER this function returns and after harness
    wiring runs, so everything the day-one scaffold produces gets staged
    together (see :func:`init_git`'s own docstring for why that ordering
    matters). Defaults to ``True`` -- the pre-existing default every caller
    that predates this field already assumed -- so a caller that never mentions
    git gets the identical ``smairt.yaml`` (no ``settings.git`` key at all) it
    always got; see :func:`render_identity` for why the key is omitted rather
    than written as ``true``.
    """
    researcher = Researcher(name=researcher).name
    if not description.strip():
        raise ValueError("description must not be empty")

    today = created or date.today()
    version = scaffold_version or __version__
    question = question.strip() if question and question.strip() else None
    expertise = expertise.strip() if expertise and expertise.strip() else None

    # smairt.yaml is the project's identity file (name, researcher, harness) --
    # written first so every later step happens inside a folder that
    # find_project_root() can already recognize as a SMAIRT project.
    write_once(
        root / "smairt.yaml",
        render_identity(
            name, researcher, description, harness, today, version, expertise=expertise, git=git
        ),
    )

    # STATUS.md starts with the paper note as its one open question, if the
    # researcher said this project expects to support a paper -- a nudge
    # toward the (currently deferred) Paper overlay, not a real feature yet.
    open_questions = [_PAPER_NOTE] if paper else []
    write_once(
        root / "STATUS.md", render_status(today, description, open_questions, focus=question)
    )
    write_once(root / "AGENTS.md", render_agents_md(name, description, expertise=expertise))
    # CLAUDE.md is the 2-line bridge so Claude Code (which reads CLAUDE.md,
    # not AGENTS.md) still ends up following the same one contract as every
    # other harness -- see CLAUDE_BRIDGE below.
    write_once(root / "CLAUDE.md", CLAUDE_BRIDGE)
    write_once(root / ".gitignore", _GITIGNORE)

    write_once(root / "background" / "README.md", _BACKGROUND_README)
    write_once(root / "background" / "question.md", _render_question_md(description, question))
    write_once(root / "background" / "literature" / ".gitkeep", "")
    write_once(root / "background" / "prior_work" / ".gitkeep", "")

    write_once(root / "data" / "README.md", _DATA_README)
    write_once(root / "scripts" / "README.md", _SCRIPTS_README)
    write_once(root / "experiments" / "README.md", _EXPERIMENTS_README)

    # results/INDEX.md is derived, not a skeleton (Part I, foundation 3): it's
    # generated fresh here rather than written from a template string, and
    # every later smairt command that touches units regenerates it too.
    (root / "results").mkdir(parents=True, exist_ok=True)
    index.write_index(root)

    if hpc:
        write_once(root / "hpc" / "README.md", _HPC_README)
        write_once(root / "hpc" / "submit.slurm.example", _HPC_TEMPLATE)

    return root


def is_git_work_tree(path: Path) -> bool:
    """Is ``path`` inside a usable Git working tree — its own, or one that starts above it?

    Public and shared: :func:`init_git` below uses it to decide whether
    ``root`` already sits inside somebody else's repository (a lab
    monorepo, a researcher's whole project tree already one repo, ...),
    and :mod:`smairt.check` uses the identical check to decide whether rule
    SMAIRT004 (log immutability) has any Git history to inspect at all. One
    implementation, not two copies to keep in sync: checks that a ``git``
    executable is even on PATH, then that ``git rev-parse
    --is-inside-work-tree`` succeeds from ``path`` — the same test Git
    itself uses, so it correctly says ``True`` even when ``path`` is nested
    several directories under the repo's actual root, not just when
    ``path`` IS that root.
    """
    if shutil.which("git") is None:
        return False
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=path,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


@dataclass(frozen=True)
class GitInitResult:
    """What :func:`init_git` did, or deliberately did not do.

    Three outcomes, not a single ``str | None`` — the old shape conflated
    "did nothing because everything's already fine" with "did nothing
    because something went wrong," which made the CLI unable to tell a
    true "skipped on purpose" apart from a warning, or from success.

    * ``"initialized"`` — a fresh repo was created at ``root`` and the
      scaffold staged. ``message`` is empty; there's nothing more to say.
    * ``"skipped"`` — deliberately did nothing. ``message`` explains why
      (already a repo at ``root``, or ``root`` sits inside one that starts
      above it — see :func:`init_git`).
    * ``"warning"`` — git is missing or a command failed. ``message``
      explains what. Project creation itself still succeeded either way;
      this is advisory only.
    """

    outcome: Literal["initialized", "skipped", "warning"]
    message: str


def init_git(root: Path) -> GitInitResult:
    """``git init`` + ``git add -A`` at ``root``: stage the scaffold, never commit it.

    Restores a habit the pre-rebuild SMAIRT had and the v2 rebuild dropped:
    collaboration is the point of the whole tool (``smairt.yaml``, ``AGENTS.md``,
    the generated harness wiring, and the CI workflow only do their job once
    every researcher who clones the project has the same files), so ``smairt
    new`` should leave a project one ``git commit`` away from being shared
    rather than silently ungit'd.

    Committing is deliberately NOT done here — that is the researcher's own
    act (a message, a moment of "this is worth recording"), not something a
    scaffolding tool should do on their behalf.

    Two distinct reasons this backs off instead of running ``git init``,
    both reported as ``"skipped"`` (never a warning — both are the correct
    outcome, not a failure):

    * ``root/.git`` already exists — calling this against a project a
      researcher already ``git init``'d themselves is always safe.
    * ``root`` is nested inside a Git work tree that starts ABOVE it (a lab
      monorepo, a researcher's whole project tree already one repo, ...).
      Running plain ``git init`` here would silently create a SECOND repo
      nested inside the first — invisible to the outer repo (an untracked
      directory, not even a gitlink), so a collaborator cloning the outer
      repo gets nothing and the researcher's commits live somewhere nobody
      else knows to look. :func:`is_git_work_tree` is what detects this
      case; a bare ``(root / ".git").exists()`` check only catches the
      first bullet, not this one.

    Deliberately does NOT fall back to ``git add``-ing the scaffold into
    that OUTER repo either, in the second case: staging files into a
    repository the researcher never told ``smairt new`` to touch is a
    bigger surprise than leaving the new files untracked, and ``git
    status`` in that outer repo will show them as untracked immediately
    regardless — the researcher decides whether and how to bring them in.

    Warn, don't fail: a missing ``git`` executable or a failing subprocess
    call returns ``"warning"`` with a human-readable message instead of
    raising, the same idiom :mod:`smairt.check` uses for a missing Git —
    project creation itself must still succeed even when Git doesn't
    cooperate.
    """
    if (root / ".git").exists():
        return GitInitResult("skipped", "this project is already a Git repository.")
    if is_git_work_tree(root):
        return GitInitResult(
            "skipped",
            "this project sits inside an existing Git repository, so Git was left "
            "alone rather than nesting a second one. The scaffold shows up as "
            "untracked there — add and commit it when you're ready.",
        )
    try:
        init_result = subprocess.run(
            ["git", "init"], cwd=root, capture_output=True, text=True, check=False
        )
        if init_result.returncode != 0:
            return GitInitResult(
                "warning", f"git init failed: {(init_result.stderr or init_result.stdout).strip()}"
            )
        add_result = subprocess.run(
            ["git", "add", "-A"], cwd=root, capture_output=True, text=True, check=False
        )
        if add_result.returncode != 0:
            return GitInitResult(
                "warning", f"git add failed: {(add_result.stderr or add_result.stdout).strip()}"
            )
    except FileNotFoundError:
        return GitInitResult(
            "warning",
            "git is not installed; skipping git init (run it yourself once git is available).",
        )
    return GitInitResult("initialized", "")


def render_identity(
    name: str,
    researcher: str,
    description: str,
    harness: Harness,
    created: date,
    scaffold_version: str,
    *,
    adoption: Mapping[str, object] | None = None,
    expertise: str | None = None,
    git: bool = True,
) -> str:
    """Render ``smairt.yaml`` (Part II schema). Shared by ``smairt new`` and
    ``smairt adopt`` — the latter passes ``adoption`` (``adopted``/``date``/
    ``known_folders``), the only schema addition adoption makes.

    ``expertise`` is an OPTIONAL top-level key, omitted entirely (never written
    as ``expertise: null`` or ``expertise: ""``) when not given -- a project that
    never answered the prompt must read exactly as it did before this field
    existed, both to a human scanning the file and to
    :mod:`smairt.check`'s SMAIRT011 rule, whose required-field list
    (:data:`smairt.check._PROJECT_CONFIG_REQUIRED_FIELDS`) deliberately does NOT
    include it: an absent ``expertise:`` is a researcher who hasn't said yet,
    not a finding, and must never become one just because a key happens to be
    missing. A blank/whitespace-only value is treated as "not given" by
    :func:`create_project` before it ever reaches this function, so the only
    two states this function itself has to render are "the key is present with
    real text" and "the key does not exist" -- never a present-but-empty
    middle state that would need its own handling everywhere the field is read.

    ``git`` mirrors that same "present only when it says something" shape for
    ``settings.git``, but the polarity is inverted for a different reason:
    ``settings.strict_hooks`` (this function's other ``settings`` key) is
    always written because ``False`` is its own meaningful, common default a
    reader needs to see -- there is no ambiguity to avoid. ``settings.git``
    exists purely so SMAIRT101 (raw-log immutability can't be checked) can
    tell "this researcher deliberately chose no Git" from "this project just
    hasn't run ``git init`` yet" once both look identical on disk (no
    ``.git`` either way). Only the deliberate-opt-out case needs recording --
    the default, git-enabled case needs no marker at all, since that's what
    "the key is absent" already means everywhere else in this schema. Writing
    ``settings.git: true`` on every project that took the (also default)
    ``smairt new`` git prompt would be pure noise: one more line every
    existing project (and every test asserting this schema's exact shape)
    would have to carry for a fact that was already true by default.
    """
    config: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "scaffold_version": scaffold_version,
        "name": name,
        "researcher": researcher,
        "description": description,
    }
    # Inserted here (right after description, before created:) rather than
    # tacked onto the end -- expertise is an identity field, same family as
    # name/researcher/description, and reads best grouped with them.
    if expertise:
        config["expertise"] = expertise
    config["created"] = created
    config["harnesses"] = [] if harness is Harness.none else [harness.value]
    settings: dict[str, object] = {"strict_hooks": False}
    if not git:
        settings["git"] = False
    config["settings"] = settings
    if adoption is not None:
        config["adoption"] = dict(adoption)
    return yaml.safe_dump(config, sort_keys=False, default_flow_style=False, allow_unicode=True)


_DEFAULT_NEXT_STEP = "Create the first stage or question with `smairt unit new`."


def render_status(
    today: date,
    description: str,
    open_questions: Sequence[str],
    *,
    next_step: str = _DEFAULT_NEXT_STEP,
    focus: str | None = None,
) -> str:
    """Render ``STATUS.md``. Shared by ``smairt new`` and ``smairt adopt`` — the
    latter passes its own seeded ``next_step`` text.

    ``focus`` lets a caller put something OTHER than ``description`` in the
    ``## Focus`` section without changing ``description``'s own meaning
    everywhere else it's used (the short filing label in ``smairt.yaml`` and
    ``AGENTS.md``'s title line). The one caller that passes it is
    :func:`create_project`, when the researcher answered ``smairt new``'s
    big-question prompt: the question, not the one-line description, is what
    should orient a returning researcher (or ``smairt status``'s "Focus:"
    line), because a filing label like "Computational Biology" was never
    meant to answer "what is this project actually trying to find out."
    Defaults to ``None``, which falls back to ``description`` -- the exact
    behavior this function always had -- so every caller that predates this
    parameter (``smairt adopt``, and ``smairt new`` whenever the question was
    skipped) renders byte-identical output.
    """
    lines = [
        "## Focus",
        focus if focus is not None else description,
        "",
        "## Next",
        next_step,
        "",
        "## Open questions",
        *[f"- {item}" for item in open_questions],
        "",
        "## Decisions",
        "",
    ]
    return frontmatter.render({"updated": today}) + "\n" + "\n".join(lines) + "\n"


def _render_question_md(description: str, question: str | None = None) -> str:
    """Render ``background/question.md``.

    Two shapes, depending on whether the researcher answered ``smairt new``'s
    big-question prompt:

    * ``question`` given: it becomes the file's body outright, with a short
      framing line making clear this is the file the whole project hangs
      off -- the researcher already did the hard part (phrasing it), so
      there's nothing left to prompt them to replace.
    * ``question`` absent (``None``, the default): the exact placeholder
      behavior this function always had -- seeded with ``description`` and an
      instruction to replace it, so every existing caller (``smairt new``
      whenever the prompt is skipped -- the common, explicitly-supported
      case) renders byte-identical output to before this parameter existed.
      ``smairt adopt`` never calls this function at all (adoption is
      contract-around, not question-first -- see :mod:`smairt.adopt`'s module
      docstring), so it is unaffected either way.
    """
    if question:
        return (
            "# The question\n\n"
            f"{question}\n\n"
            "This is the project's big question -- the one everything under "
            "`experiments/` answers. It should stay stable while that work moves.\n"
        )
    return (
        "# The question\n\n"
        f"{description}\n\n"
        "Replace this with the project's big question: the one everything else here "
        "answers. It should stay stable while the work under `experiments/` moves.\n"
    )


_PAPER_NOTE = "Paper support (a `paper/` overlay) is deferred until real paper work begins."


def render_agents_md(name: str, description: str, *, expertise: str | None = None) -> str:
    """The canonical AGENTS.md contract (spec WP5): ~1 page, tier-3 guidance only.

    Everything tier-1 (generated) or tier-2 (checked) can carry is a command
    reference here, not restated as prose — see Part I, foundation 2. Kept
    under the ~120-line cap (including the ``## Project learnings`` header)
    by :mod:`tests.test_project`. Shared by ``smairt new`` and ``smairt
    adopt`` (one contract, generated the same way everywhere — spec Part I
    foundation 2) — the ONE rendering function, no duplicate template.

    ``expertise`` is optional and, when given, adds one short section right
    under the title: "## Who you're working with". This is deliberately NOT
    folded into the title line itself (``{name}: {description}``) — that line
    is the short filing label a researcher scans first, and a whole
    field/tooling-comfort sentence stapled onto it would make even the
    common, no-expertise case's title line unpredictable in length. A
    dedicated section, by contrast, costs the no-expertise case nothing (it's
    just absent) and gives an assistant something concrete to point back to:
    AGENTS.md's own "## The explanation rule" section already says every
    notable-or-above proposal must be stated "in plain language" — until now
    that instruction had no way to know what "plain" means for THIS
    researcher (jargon-heavy is exactly "plain" for a specialist in their own
    field, and exactly the opposite for someone new to the tooling). This
    section is what finally gives that existing rule a researcher-specific
    target instead of one guess-worthy adjective.

    Kept as string concatenation (header text built here, ``## Shape``
    onward still the fixed :data:`_AGENTS_BODY` constant) rather than one
    ``.format()`` call against a single template, specifically so the
    no-expertise case's output stays byte-identical to what this function
    produced before ``expertise`` existed — every project, and every
    existing golden-fixture comparison, that never answers the prompt must
    see zero drift.
    """
    header = f"# AGENTS.md\n\n{name}: {description}\n"
    if expertise:
        header += (
            "\n## Who you're working with\n\n"
            f"{expertise} -- calibrate jargon and explanations to this, not the "
            "reverse, per The explanation rule below.\n"
        )
    return header + "\n" + _AGENTS_BODY


_AGENTS_BODY = """\
## Shape

```
my_project/
├── smairt.yaml       # identity: name, researcher, harnesses
├── STATUS.md         # intent: focus / next / open questions / decisions
├── AGENTS.md         # this file: the contract + project learnings
├── CLAUDE.md         # bridge: imports this file for Claude Code
├── .gitignore
├── background/       # question.md, literature/, prior_work/ — context, never code
├── data/             # one subfolder per dataset, each with provenance
├── scripts/          # shared reusable code, called by experiments with parameters
├── experiments/      # the work: numbered stages + dated questions
└── results/          # results/INDEX.md — GENERATED signpost: evidence -> unit
```

## Units

Two kinds, both under `experiments/`: a **stage** (`NN_name/`, one step of the
spine) and a **question** (`YYYY-MM-DD_name/`, one exploratory probe). Every
unit gets the same three subfolders: `logs/`, `out/`, `figures/`.

Three cases: **own code** (scripts live in the unit or in `scripts/`, called
with `params:` — the normal case); **outside tool** (the unit is a receipt:
config, exact command, raw log, `tool:`/`tool_version:` pinned in
frontmatter — the tool itself is never copied in); **referenced elsewhere**
(a thin, README-only unit pointing at code that already exists outside
`experiments/` — how a pre-existing project gets adopted).

`smairt unit new stage|question` is the ONLY way to create a unit — it is
the sole numbering and dating authority. Never `mkdir` one by hand.

When a result raises a *new* question, record where it came from:
`smairt unit new question --from <the-unit-that-raised-it>`. The test for
whether it earns its own unit is whether you can state a new testable claim
in one line — if you can, it is a new question; if not, it is still part of
the one you are already in.

## Frontmatter duties

Every unit README opens with a YAML block. Keep `status` current; closing a
question needs a one-line `verdict` and a non-empty `## Analysis plan`
section in the same edit. A verdict answers only its own stated
`hypothesis:` — a finding that isn't about that line belongs in its own
unit, never retrofitted into this one. If the plan changes for a real
reason, keep the original text and append `**Amended <YYYY-MM-DD>:**` plus
what changed and why, rather than rewriting it. A dead end is a status
change in place (`status: dead-end` + why, in one line) — never move or
delete the folder. Every evidence pointer (`script:`, `log:`, `outputs:`)
must resolve to a real path; `smairt check` verifies this.

## Evidence rules

Raw logs, once written, are never edited again. Every claim under "What it
means" points at the log (or figure) that backs it — no unsourced claims.
Data files carry a short provenance note: where they came from, when, what
was already done to them before they landed in `data/`. Record where a
dataset's bytes physically live with `smairt data new`/`smairt data
locate` — never a new convention of your own.

## The loop

question -> hypothesis + analysis plan (both written before the run) ->
run (log captured) -> **What happened** (facts, only what the log shows) ->
**What it means** (your interpretation) -> verdict + STATUS.md update ->
next question.

## The stakes rule

Label every proposal you make **routine**, **notable**, or **structural**.
Routine flows without asking. Notable gets a heads-up but doesn't block.
Structural — a new top-level folder, reorganizing the spine, deleting
anything, changing a frozen stage — needs the researcher's explicit yes
before you act.

## The explanation rule

Any notable-or-above proposal states, in plain language: (a) what it does,
(b) what it risks scientifically, (c) one alternative and why not chosen.
Never present one option as the only way — the researcher evaluates the
tradeoff, you don't make it for them.

## Practices

Prefer cheap or synthetic data before expensive or real data — a practice,
not a folder. Prefer extending a script in `scripts/` over writing a
near-duplicate (that's a notable proposal). Run `smairt status` when you
join a session; run `smairt check` before you end one. At session end,
propose a 3-line STATUS.md update (focus / next / one open question).

## Project learnings

<!-- Append project-specific patterns and solved errors here as they come
     up; prune as you append. Keep this whole file under ~120 lines. -->
"""

# The 2-line Claude Code bridge (spec Part II): imports AGENTS.md so Claude Code,
# which reads CLAUDE.md and not AGENTS.md natively, still gets the same contract as
# every other harness. Public so smairt.connect can reuse it verbatim (WP4).
CLAUDE_BRIDGE = """\
# SMAIRT
@AGENTS.md
"""

_GITIGNORE = """\
# Byte-compiled / cache
__pycache__/
*.py[cod]
.mypy_cache/
.pytest_cache/
.ruff_cache/

# Environments
.venv/
.env

# Editors and OS noise
.DS_Store
.vscode/
.idea/
*.swp

# Large or generated data: uncomment patterns as this project needs them
# *.bam
# *.fastq.gz
# *.h5ad

# Data files live on disk or on an HPC, not in git — the per-dataset READMEs
# record where. Delete these lines to track a small dataset directly.
data/**
!data/README.md
!data/*/
!data/*/README.md
"""

_BACKGROUND_README = """\
# background/

Context, never code. `question.md` holds the project's big question — stable across
the whole project. `literature/` holds papers and notes; `prior_work/` holds related
prior efforts. Nothing here runs; it orients.
"""

_DATA_README = """\
# data/

One subfolder per dataset, created with `smairt data new NAME`. Each README's
frontmatter records every place the dataset's bytes actually live (local path, HPC
host + path, or a source URL) — add more with `smairt data locate NAME`, see them
all with `smairt data list`. Below the frontmatter: free-form provenance prose,
where the data came from, when, and any transform already applied before it landed
here. Data file contents are git-ignored by default (see .gitignore); only the
READMEs are tracked.
"""

_SCRIPTS_README = """\
# scripts/

Shared, reusable code: anything called by more than one experiment, invoked with
parameters. One-off probe code stays inside the unit that uses it. Prefer extending
a script here over writing a near-duplicate.
"""

_EXPERIMENTS_README = """\
# experiments/

The work, as units. A **stage** (`NN_name/`) is one step of the spine; a
**question** (`YYYY-MM-DD_name/`) is one exploratory probe. Numbered folders sort
above dated ones, so the spine reads top-down. Create units with
`smairt unit new stage` or `smairt unit new question` — never by hand.
"""

_HPC_README = """\
# hpc/

SLURM submission templates for this project. Copy `submit.slurm.example`, edit it
for the job at hand, and keep the copy inside the stage or question it belongs to.
"""

_HPC_TEMPLATE = """\
#!/bin/bash
# Example SLURM submission script. Copy this into the unit it belongs to, rename
# it, and edit the directives below for the job at hand.
#
#SBATCH --job-name=CHANGE_ME
#SBATCH --output=logs/%x-%j.out
#SBATCH --error=logs/%x-%j.err
#SBATCH --time=01:00:00
#SBATCH --mem=8G
#SBATCH --cpus-per-task=4
#SBATCH --partition=CHANGE_ME

# module load / conda activate / source whatever this job needs here.

# srun my_command --with these --args
"""
