"""Tests for the installed-skills lookup (src/smairt/skills.py).

Covers list_skills()/read_skill() against the package's real assets/skills/
directory (import machinery, not a fixture) plus the UnknownSkillError case,
following tests/test_frontmatter.py for the shape of a small-module test file.
"""

from __future__ import annotations

import pytest

from smairt.skills import UnknownSkillError, list_skills, read_skill

_EXPECTED_SKILLS = (
    "smairt-adopt",
    "smairt-adversarial-review",
    "smairt-close-question",
    "smairt-fork",
    "smairt-new-project",
    "smairt-new-question",
    "smairt-new-stage",
    "smairt-orient",
)


def test_list_skills_returns_every_shipped_skill_sorted() -> None:
    assert list_skills() == list(_EXPECTED_SKILLS)


def test_read_skill_returns_frontmatter_naming_the_skill_itself() -> None:
    for name in _EXPECTED_SKILLS:
        text = read_skill(name)
        assert text.startswith("---\n")
        assert f"name: {name}\n" in text


def test_read_skill_rejects_an_unknown_name() -> None:
    with pytest.raises(UnknownSkillError):
        read_skill("smairt-does-not-exist")
