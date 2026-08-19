"""Tests for the frontmatter reader/writer (src/smairt/frontmatter.py).

Covers round-tripping a YAML block through render() then parse(), and the
malformed-input cases that should raise FrontmatterError.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from smairt.frontmatter import FrontmatterError, parse, read, render


def test_render_then_parse_round_trips_fields_and_body() -> None:
    fields = {
        "kind": "stage",
        "title": "Alignment",
        "status": "active",
        "created": date(2026, 1, 1),
    }
    text = render(fields) + "\nBody line one.\n"

    parsed_fields, body = parse(text)

    assert parsed_fields == fields
    assert body == "\nBody line one.\n"


def test_render_produces_a_dash_delimited_block() -> None:
    text = render({"kind": "question"})

    assert text.startswith("---\n")
    assert "kind: question\n---\n" in text


def test_parse_rejects_text_without_a_frontmatter_block() -> None:
    with pytest.raises(FrontmatterError):
        parse("# Just a heading\n\nNo frontmatter here.\n")


def test_parse_rejects_a_non_mapping_frontmatter_block() -> None:
    with pytest.raises(FrontmatterError):
        parse("---\n- one\n- two\n---\nbody\n")


def test_read_parses_a_file_on_disk(tmp_path: Path) -> None:
    path = tmp_path / "README.md"
    path.write_text(render({"kind": "stage"}) + "\n## Section\n", encoding="utf-8")

    fields, body = read(path)

    assert fields == {"kind": "stage"}
    assert "## Section" in body
