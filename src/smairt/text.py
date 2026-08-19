from __future__ import annotations

import re

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify(text: str, *, fallback: str = "untitled", sep: str = "_") -> str:
    """Turn free text into a filesystem-safe, lowercase slug.

    Project folders use the default underscore separator; unit slugs pass
    ``sep="-"`` so the date/number prefix's underscore stays visually distinct
    (``2026-08-12_replicate3-pca``, per spec Part II).
    """
    slug = _NON_ALNUM.sub(sep, text.strip().lower()).strip(sep)
    return slug or fallback
