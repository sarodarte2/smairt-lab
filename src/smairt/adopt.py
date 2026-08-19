"""``smairt adopt`` — contract-around adoption for a pre-existing project (stretch goal).

Spec Part II, "The three unit cases," case 3: *pre-existing project*. Ticket 06's
resolved decision governs this module's shape: **contract-around, move-nothing,
proposal-gated** — "SMAIRT arrives late and behaves like a guest." This module
writes only the contract files (:func:`adopt_project`); it never moves, renames,
or edits anything that already exists in the adopted directory. Reference units
(the proposal-gated part of adoption) are :func:`smairt.units.create_stage` /
:func:`smairt.units.create_question` called with ``ref_paths`` — see
``skills/smairt-adopt/SKILL.md`` for the walking procedure an assistant follows
after this command runs.

Public entry point: :func:`adopt_project`, returning an :class:`AdoptResult`.

Judgment calls a reviewer should know about
--------------------------------------------
* AGENTS.md is rendered by the exact same :func:`smairt.project.render_agents_md`
  function ``smairt new`` uses — byte-identical content, including the "Shape"
  diagram that names ``background/``/``data/``/``scripts/`` even though adopt
  never creates them. The contract is one thing, generated the same way
  everywhere (Part I, foundation 2); it documents where later growth should go,
  not the literal folder listing of any one project today.
* Adopt writes only what the spec's stretch-goal section names as "the contract
  files": ``smairt.yaml``, ``STATUS.md``, ``AGENTS.md``, ``results/INDEX.md``,
  and ``experiments/`` + its README. Unlike ``smairt new`` it does NOT write a
  ``.gitignore`` — an adopted project's existing ignore rules (if any) are left
  alone, and adopt has no basis for guessing what this codebase should ignore.
* ``known_folders`` records every non-hidden top-level directory present at
  adoption time, not just the ones outside the standard scaffold set — useful
  as a complete map for the ``smairt-adopt`` skill to walk, even when a
  pre-existing folder happens to share a name with a recognized scaffold
  directory (e.g. an existing ``data/``).
* Harness wiring is delegated entirely to :func:`smairt.connect.connect` (same
  call `smairt new` makes) rather than re-implemented here: CLAUDE.md is only
  ever written by the Claude Code handler, so "CLAUDE.md only if harness
  claude-code chosen" falls out of reusing that logic rather than being a
  separate rule in this module.
* The "looks like a SMAIRT tool checkout" refusal is a heuristic
  (``pyproject.toml`` naming a ``smairt`` project), not a guarantee — it is
  meant to catch the obvious self-adoption mistake, not every possible one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from smairt import __version__, index
from smairt.connect import ConnectResult, connect
from smairt.fsutil import write_or_warn
from smairt.models import Researcher
from smairt.project import Harness, render_agents_md, render_identity, render_status

_ADOPT_NEXT_STEP = (
    "Walk the existing folders with the smairt-adopt skill and create reference "
    "units for what matters."
)

_EXPERIMENTS_README = """\
# experiments/

The work, as units. A **stage** (`NN_name/`) is one step of the spine; a
**question** (`YYYY-MM-DD_name/`) is one exploratory probe. Numbered folders sort
above dated ones, so the spine reads top-down. Create units with
`smairt unit new stage` or `smairt unit new question` — never by hand.

This project was adopted (`smairt adopt`): the folders alongside this one
predate SMAIRT and were not moved here. `smairt unit new ... --ref <path>`
creates a thin, README-only unit that points at one of them instead.
"""


class NotAdoptableError(ValueError):
    """Raised when ``smairt adopt`` refuses to run against a directory."""


@dataclass(frozen=True)
class AdoptResult:
    """What one :func:`adopt_project` call did."""

    root: Path
    known_folders: tuple[str, ...]
    written: tuple[str, ...]
    skipped: tuple[str, ...]
    warned: tuple[str, ...]
    connect_result: ConnectResult | None


def _looks_like_smairt_checkout(root: Path) -> bool:
    """True if ``root`` looks like the SMAIRT tool's own repo, not a research project."""
    pyproject = root / "pyproject.toml"
    if not pyproject.is_file():
        return False
    try:
        text = pyproject.read_text(encoding="utf-8")
    except OSError:
        return False
    return 'name = "smairt"' in text or "name = 'smairt'" in text


def _known_folders(root: Path) -> list[str]:
    """List every non-hidden top-level folder already at ``root``, alphabetically.

    Recorded into ``smairt.yaml``'s ``adoption.known_folders`` as a map of
    what pre-existed adoption (see module docstring) — used both by
    ``smairt check``'s structure-drift rule (so these don't warn) and by the
    ``smairt-adopt`` skill (as the list of folders to walk).
    """
    return sorted(
        entry.name for entry in root.iterdir() if entry.is_dir() and not entry.name.startswith(".")
    )


def adopt_project(
    root: Path,
    *,
    name: str,
    researcher: str,
    description: str,
    harness: Harness = Harness.claude_code,
    created: date | None = None,
    scaffold_version: str | None = None,
) -> AdoptResult:
    """Lay the contract files around the pre-existing directory at ``root``.

    Moves nothing: every file already in ``root`` is left exactly where it is.
    Refuses if ``root`` is already a SMAIRT project, is empty, or looks like the
    SMAIRT tool's own checkout (see module docstring). Any contract file that
    already exists with different content (e.g. a researcher-authored
    ``AGENTS.md``) is warned about and left untouched — the same
    :func:`smairt.fsutil.write_or_warn` policy ``smairt connect`` uses.
    """
    researcher = Researcher(name=researcher).name
    if not description.strip():
        raise ValueError("description must not be empty")

    if not root.is_dir():
        raise NotAdoptableError(
            f"{root} is not an existing directory; use `smairt new` to create one."
        )
    if (root / "smairt.yaml").is_file():
        raise NotAdoptableError(f"{root} is already a SMAIRT project (smairt.yaml exists).")
    if not any(root.iterdir()):
        raise NotAdoptableError(f"{root} is empty; use `smairt new` to start a fresh project here.")
    if _looks_like_smairt_checkout(root):
        raise NotAdoptableError(
            f"{root} looks like the SMAIRT tool's own checkout (pyproject.toml names a "
            "'smairt' project), not a research project; refusing to adopt it."
        )

    known_folders = _known_folders(root)
    today = created or date.today()
    version = scaffold_version or __version__

    written: list[str] = []
    skipped: list[str] = []
    warned: list[str] = []

    # Small local helper so each contract file below is one line: write it,
    # then sort the result into written/skipped/warned depending on what
    # write_or_warn (smairt.fsutil) decided to do with it.
    def _write(relative: str, content: str) -> None:
        status, warning = write_or_warn(root, relative, content)
        if status == "written":
            written.append(relative)
        elif status == "skipped":
            skipped.append(relative)
        else:
            assert warning is not None
            warned.append(warning)

    # A fresh `date` object, not `today` itself: PyYAML aliases (`&id001`/`*id001`)
    # two dumped values that are the same object, which is valid but odd for a
    # researcher reading smairt.yaml directly (Part I, foundation 7: both readers).
    adoption = {
        "adopted": True,
        "date": date(today.year, today.month, today.day),
        "known_folders": known_folders,
    }
    _write(
        "smairt.yaml",
        render_identity(name, researcher, description, harness, today, version, adoption=adoption),
    )
    _write("STATUS.md", render_status(today, description, [], next_step=_ADOPT_NEXT_STEP))
    _write("AGENTS.md", render_agents_md(name, description))
    _write("experiments/README.md", _EXPERIMENTS_README)

    index.write_index(root)  # results/INDEX.md is derived, not a skeleton — always regenerated
    written.append("results/INDEX.md")

    connect_result: ConnectResult | None = None
    if harness is not Harness.none:
        connect_result = connect(root, harness, strict=False)

    return AdoptResult(
        root=root,
        known_folders=tuple(known_folders),
        written=tuple(written),
        skipped=tuple(skipped),
        warned=tuple(warned),
        connect_result=connect_result,
    )
