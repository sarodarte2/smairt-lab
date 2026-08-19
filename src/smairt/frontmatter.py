from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping

import yaml

_BLOCK_RE = re.compile(r"\A---\n(?P<yaml>.*?)\n---\n?(?P<body>.*)\Z", re.DOTALL)


class FrontmatterError(ValueError):
    """Raised when a unit README's frontmatter block is missing or malformed."""


def render(data: Mapping[str, Any]) -> str:
    """Render ``data`` as a ``---`` delimited YAML frontmatter block.

    Key order is preserved (callers pass an already-ordered mapping) so generated
    files match the field order shown in the spec's schemas.
    """
    yaml_text = yaml.safe_dump(
        dict(data), sort_keys=False, default_flow_style=False, allow_unicode=True
    ).rstrip("\n")
    return f"---\n{yaml_text}\n---\n"


def parse(text: str) -> tuple[dict[str, Any], str]:
    """Split a file's leading frontmatter block from its body.

    Returns ``(fields, body)``. Raises :class:`FrontmatterError` if the file has no
    well-formed ``---``-delimited block at its start. This is a structural parser
    only: it never inspects or judges the researcher's prose in the body.
    """
    match = _BLOCK_RE.match(text)
    if not match:
        raise FrontmatterError("file does not open with a well-formed frontmatter block")
    data = yaml.safe_load(match.group("yaml"))
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise FrontmatterError("frontmatter block must be a YAML mapping")
    return data, match.group("body")


def read(path: Path) -> tuple[dict[str, Any], str]:
    """Read and parse the frontmatter block of the file at ``path``."""
    return parse(path.read_text(encoding="utf-8"))
