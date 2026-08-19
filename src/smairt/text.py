"""Turns free-text titles into filesystem-safe folder names ("slugs").

Used across the codebase wherever a researcher's typed title (e.g. "Align
reads to reference") needs to become part of a folder name (e.g. "align_reads
to reference" -> ``align_reads-to-reference``). This is the only place that
logic lives, so every folder name in the project is built the same way.
"""

from __future__ import annotations

import re

# Matches any run of characters that is NOT a lowercase letter or digit, so we
# can replace whole runs of spaces/punctuation with a single separator in one
# pass (e.g. "Replicate #3!!" -> "replicate_3").
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify(text: str, *, fallback: str = "untitled", sep: str = "_") -> str:
    """Turn free text into a filesystem-safe, lowercase slug.

    Example: ``slugify("Align reads")`` -> ``"align_reads"``.

    Project folders use the default underscore separator; unit slugs pass
    ``sep="-"`` so the date/number prefix's underscore stays visually distinct
    (``2026-08-12_replicate3-pca``, per spec Part II).

    If ``text`` has nothing left after stripping punctuation (e.g. an empty
    string, or a title made entirely of symbols), ``fallback`` is returned
    instead of an empty string — callers never have to check for that case.
    """
    slug = _NON_ALNUM.sub(sep, text.strip().lower()).strip(sep)
    return slug or fallback
