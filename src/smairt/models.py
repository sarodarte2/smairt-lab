from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator


class Researcher(BaseModel):
    """A project's researcher identity, as recorded in ``smairt.yaml``.

    Kept minimal on purpose (Part II, ``smairt.yaml``): identity changes rarely and
    research state never lives here.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    email: str | None = None

    @field_validator("name")
    @classmethod
    def require_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Researcher name must not be empty.")
        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        return value or None
