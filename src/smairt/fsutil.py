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


def write_or_warn(project_root: Path, relative: str, content: str) -> tuple[str, str | None]:
    """Write ``content`` to ``project_root / relative`` unless a differing file exists.

    The idempotent, researcher-respecting write policy shared by ``smairt connect``
    and ``smairt adopt`` (Part I, foundation 5: human edits are first-class):
    identical content already there is a no-op; a missing file is written; a
    present-but-different file is assumed researcher-edited and is left
    untouched, with a warning.

    Returns ``(status, warning)`` where ``status`` is one of ``"written"``,
    ``"skipped"``, ``"warned"``; ``warning`` is a human-readable message when
    ``status == "warned"``, else ``None``.
    """
    path = project_root / relative
    if path.is_file():
        if path.read_text(encoding="utf-8") == content:
            return "skipped", None
        return "warned", (
            f"{relative} already exists and differs from the generated version; "
            "left untouched (looks researcher-edited)."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return "written", None
