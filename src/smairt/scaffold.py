from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Literal, Mapping

import yaml
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

AssetKind = Literal["directory", "file"]
AssetOwnership = Literal[
    "tool-guidance", "editable-starter", "researcher-work", "historical-reference"
]
AssetCondition = Literal["always", "hpc"]


class ScaffoldAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    path: str
    kind: AssetKind
    purpose: str
    ownership: AssetOwnership
    condition: AssetCondition
    source: str | None = None

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or value in {"", "."}:
            raise ValueError("scaffold asset paths must be safe relative paths")
        return value

    @model_validator(mode="after")
    def validate_source(self) -> ScaffoldAsset:
        if self.kind == "file" and self.source is None:
            raise ValueError("file assets require a source")
        if self.kind == "directory" and self.source is not None:
            raise ValueError("directory assets cannot define a source")
        return self


class ScaffoldBlueprint(BaseModel):
    """The declared shape of the generated scaffold.

    This is a manifest for review, not a template engine: ``smairt new`` and
    ``smairt unit new`` render scaffold content directly (Part III, WP1 — plain
    string formatting, no templating layer), and this file separately declares
    every path they produce so ``scripts/scaffold_diff.py`` can flag product-surface
    changes (added/removed/renamed paths, ownership or condition changes) for review.
    """

    model_config = ConfigDict(extra="forbid")

    blueprint_version: int
    assets: list[ScaffoldAsset]

    @model_validator(mode="after")
    def validate_unique_identity_and_paths(self) -> ScaffoldBlueprint:
        ids = [asset.id for asset in self.assets]
        paths = [asset.path for asset in self.assets]
        if len(ids) != len(set(ids)):
            raise ValueError("scaffold asset ids must be unique")
        if len(paths) != len(set(paths)):
            raise ValueError("scaffold asset paths must be unique")
        return self


def load_blueprint() -> ScaffoldBlueprint:
    path = Path(__file__).parent / "assets" / "scaffold-blueprint.yaml"
    return ScaffoldBlueprint.model_validate(yaml.safe_load(path.read_text()))


def diff_blueprints(
    previous: Mapping[str, object], current: Mapping[str, object]
) -> dict[str, list[str]]:
    before = _entries_by_id(previous)
    after = _entries_by_id(current)
    before_ids = set(before)
    after_ids = set(after)
    shared = sorted(before_ids & after_ids)
    return {
        "added": sorted(str(after[item]["path"]) for item in after_ids - before_ids),
        "removed": sorted(str(before[item]["path"]) for item in before_ids - after_ids),
        "renamed": [
            f"{before[item]['path']} -> {after[item]['path']}"
            for item in shared
            if before[item]["path"] != after[item]["path"]
        ],
        "ownership_changed": [
            f"{after[item]['path']}: {before[item]['ownership']} -> {after[item]['ownership']}"
            for item in shared
            if before[item]["ownership"] != after[item]["ownership"]
        ],
        "condition_changed": [
            f"{after[item]['path']}: {before[item]['condition']} -> {after[item]['condition']}"
            for item in shared
            if before[item]["condition"] != after[item]["condition"]
        ],
    }


def _entries_by_id(data: Mapping[str, object]) -> dict[str, dict[str, str]]:
    raw = data.get("assets")
    if not isinstance(raw, list):
        raise ValueError("blueprint data must contain an assets list")
    result: dict[str, dict[str, str]] = {}
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError("blueprint assets must be mappings")
        required = ("id", "path", "ownership", "condition")
        if not all(isinstance(entry.get(key), str) for key in required):
            raise ValueError("blueprint diff entries require id, path, ownership, and condition")
        result[str(entry["id"])] = {key: str(entry[key]) for key in required}
    return result
