from __future__ import annotations

import re

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify(text: str, *, fallback: str = "untitled") -> str:
    """Turn free text into a filesystem-safe, lowercase, underscore-joined slug."""
    slug = _NON_ALNUM.sub("_", text.strip().lower()).strip("_")
    return slug or fallback
