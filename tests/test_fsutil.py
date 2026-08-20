"""Tests for ``src/smairt/fsutil.py``: the shared file-write policies.

``write_once`` used to leave `mkdir`/`write_text`/`path.exists()` unguarded,
so any filesystem-level obstruction (a name too long, a read-only parent, a
plain file where a directory was expected) escaped as a raw ``OSError``
subclass instead of a message a researcher could act on. These tests
reproduce that failure directly against ``write_once`` rather than through
`smairt new`, so they don't depend on any one filesystem's exact length
limit.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from smairt.fsutil import PathExistsError, WriteError, write_once

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="permission-bit tests assume a POSIX filesystem"
)


def test_write_once_still_raises_path_exists_error_for_a_real_collision(
    tmp_path: Path,
) -> None:
    path = tmp_path / "smairt.yaml"
    path.write_text("already here\n", encoding="utf-8")

    with pytest.raises(PathExistsError):
        write_once(path, "new content\n")


def test_write_once_wraps_permission_denied_as_write_error_not_a_traceback(
    tmp_path: Path,
) -> None:
    """Regression: a read-only parent directory used to crash `smairt new` with
    a raw `PermissionError` from the unguarded `path.parent.mkdir(...)` call."""
    ro_parent = tmp_path / "ro_parent"
    ro_parent.mkdir()
    ro_parent.chmod(0o555)
    try:
        with pytest.raises(WriteError) as excinfo:
            write_once(ro_parent / "blocked" / "smairt.yaml", "content\n")
        assert str(ro_parent / "blocked" / "smairt.yaml") in str(excinfo.value)
    finally:
        ro_parent.chmod(0o755)


def test_write_once_wraps_not_a_directory_as_write_error_not_a_traceback(
    tmp_path: Path,
) -> None:
    """Regression: `--path` naming a plain file (instead of a directory) used to
    crash `smairt new` with a raw `NotADirectoryError` from `mkdir(parents=True)`
    trying to create a child underneath a file."""
    plain_file = tmp_path / "a_plain_file.txt"
    plain_file.write_text("not a directory\n", encoding="utf-8")

    with pytest.raises(WriteError) as excinfo:
        write_once(plain_file / "filepath" / "smairt.yaml", "content\n")
    assert str(plain_file / "filepath" / "smairt.yaml") in str(excinfo.value)


def test_write_once_succeeds_when_nothing_is_wrong(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "smairt.yaml"

    result = write_once(path, "content\n")

    assert result == path
    assert path.read_text(encoding="utf-8") == "content\n"
