"""Filesystem, hashing, and serialization helpers."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any


def slugify(value: str) -> str:
    """Convert user text into a stable, filesystem-safe lowercase slug."""
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return normalized or "smairt-project"


def validate_identifier(value: str, *, label: str = "identifier") -> str:
    """Reject IDs that can change path or glob matching semantics."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", value):
        raise ValueError(f"invalid {label}: {value!r}")
    return value


def ensure_within(root: Path, path: Path) -> Path:
    """Resolve a path and reject traversal or symlink escape from ``root``."""
    root = root.resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path escapes project root: {path}") from exc
    return resolved


def ensure_no_symlink(root: Path, path: Path) -> Path:
    """Resolve a contained path while rejecting every symlink component."""
    root = root.resolve()
    requested = path if path.is_absolute() else root / path
    # Resolve end-to-end first so macOS /tmp → /private/tmp prefixes compare equal.
    resolved = ensure_within(root, requested)
    relative = resolved.relative_to(root)
    if ".." in relative.parts:
        raise ValueError(f"path escapes project root: {path}")
    cursor = root
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"path contains a symlink: {path}")
    return resolved


def sha256_file(path: Path) -> str:
    """Stream a file into SHA-256 without loading large research files into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    """Return the SHA-256 digest of UTF-8 text for managed-file tracking."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def atomic_write_bytes(path: Path, content: bytes, *, mode: int | None = None) -> None:
    """Replace a file atomically and fsync it before making it visible.

    The optional mode is applied to the staged inode before replacement.  This
    matters for generated hooks: there must never be a visible interval where a
    new hook exists but is not executable.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if mode is not None:
            temporary.chmod(mode)
        temporary.replace(path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_write(path: Path, content: str, *, mode: int | None = None) -> None:
    """Replace UTF-8 text atomically so interrupted writes cannot corrupt state."""
    atomic_write_bytes(path, content.encode("utf-8"), mode=mode)


def write_json(path: Path, data: dict[str, Any]) -> None:
    """Write deterministic, human-readable JSON through the atomic writer."""
    atomic_write(path, json.dumps(data, indent=2, sort_keys=True) + "\n")


def next_numeric_id(paths: list[Path], prefix: str, width: int = 3) -> str:
    """Return the next zero-padded ID after scanning existing artifact names."""
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)")
    values: list[int] = []
    for path in paths:
        match = pattern.match(path.name)
        if match:
            values.append(int(match.group(1)))
    return f"{prefix}{max(values, default=0) + 1:0{width}d}"
