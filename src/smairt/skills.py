"""Where SMAIRT's assistant-facing skills live once the package is installed.

The eight ``smairt-*`` procedures under ``assets/skills/`` (one ``SKILL.md``
per skill — see docs/AI_SKILL_USAGE.md) ship *inside* the ``smairt`` package
itself, the same way ``assets/scaffold-blueprint.yaml`` does. An installed
``smairt`` might be running from a wheel unpacked into a site-packages
folder, or, in principle, straight out of a zip — a path built from
``__file__``'s parent directories only works for the first of those, and
silently breaks for the rest. ``importlib.resources`` is Python's supported
way of reading data that ships inside a package no matter which shape the
install takes, so this module — and nothing else — is where that lookup
happens. Every consumer (a later ``smairt connect``'s skill delivery,
``scripts/smoke_install.py``'s installed-package check, this module's own
tests) goes through :func:`list_skills` / :func:`read_skill` instead of
guessing a path.
"""

from __future__ import annotations

from importlib import resources
from importlib.resources.abc import Traversable


class UnknownSkillError(KeyError):
    """Raised by :func:`read_skill` for a name with no matching skill folder."""


def _skills_root() -> Traversable:
    """The installed package's ``assets/skills/`` folder, wherever it lives."""
    return resources.files("smairt") / "assets" / "skills"


def list_skills() -> list[str]:
    """Every skill SMAIRT ships, by folder name, sorted (e.g. ``"smairt-fork"``).

    A "skill" is any folder under ``assets/skills/`` that actually contains a
    ``SKILL.md`` — the same rule a harness's skill loader uses to decide what
    counts, so this list matches what an assistant would actually discover.
    """
    root = _skills_root()
    return sorted(
        entry.name for entry in root.iterdir() if entry.is_dir() and (entry / "SKILL.md").is_file()
    )


def read_skill(name: str) -> str:
    """The full text of one skill's ``SKILL.md``, looked up by folder name.

    Raises :class:`UnknownSkillError` rather than letting a typo surface as a
    bare ``FileNotFoundError`` from deep inside ``importlib`` — a caller (a
    later ``smairt connect``, or a test) gets a message that names the skill
    it was actually looking for.
    """
    skill_md = _skills_root() / name / "SKILL.md"
    if not skill_md.is_file():
        raise UnknownSkillError(f"no such skill: {name!r}")
    return skill_md.read_text(encoding="utf-8")
