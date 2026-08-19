"""The ``Researcher`` data shape: who owns a project, as written to smairt.yaml.

Pydantic (the ``BaseModel`` base class) gives us validation for free: build a
``Researcher(name=...)`` with bad data and it raises immediately, instead of
letting a blank name silently end up in a generated file.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator


class Researcher(BaseModel):
    """A project's researcher identity, as recorded in ``smairt.yaml``.

    Kept minimal on purpose (Part II, ``smairt.yaml``): identity changes rarely and
    research state never lives here.
    """

    # extra="forbid" means an unexpected field (e.g. a typo like `nmae:`) raises
    # instead of being silently ignored — catches mistakes early.
    model_config = ConfigDict(extra="forbid")

    name: str
    email: str | None = None

    @field_validator("name")
    @classmethod
    def require_name(cls, value: str) -> str:
        """Reject a blank or whitespace-only name; every project needs an owner."""
        if not value.strip():
            raise ValueError("Researcher name must not be empty.")
        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        """Treat an empty string the same as "no email given" (turn it into None)."""
        return value or None
