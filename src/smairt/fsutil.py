from __future__ import annotations

from pathlib import Path


class PathExistsError(RuntimeError):
    """Raised when generation would overwrite a file that already exists.

    Skeletons are written once (Part I, foundation 5): tooling never regenerates
    researcher-editable files. Every skeleton writer in this package goes through
    :func:`write_once` so that rule holds in one place.
    """


def write_once(path: Path, content: str) -> Path:
    """Write ``content`` to ``path``, refusing to overwrite an existing file."""
    if path.exists():
        raise PathExistsError(f"refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path
