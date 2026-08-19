from __future__ import annotations

from pathlib import Path

from smairt.scaffold import diff_blueprints, load_blueprint


def test_scaffold_blueprint_loads_and_is_empty_pending_wp1() -> None:
    """WP0 demolished the old scaffold; WP1 rebuilds it from spec Part II.

    Until then the blueprint carries no assets, but the loader and its schema keep
    working so WP1 can describe the new ten-item scaffold the same way.
    """
    blueprint = load_blueprint()

    assert blueprint.assets == []


def test_every_blueprint_file_source_exists_in_the_installed_package() -> None:
    blueprint = load_blueprint()
    source_root = Path(__file__).parents[1] / "src" / "smairt" / "assets" / "scaffold"

    missing = []
    for asset in blueprint.assets:
        if asset.kind != "file" or asset.source in {"contract", "license", "assistant-pointer"}:
            continue
        assert asset.source is not None
        if not (source_root / asset.source).is_file():
            missing.append(asset.source)

    assert missing == []

    declared_directories = {asset.path for asset in blueprint.assets if asset.kind == "directory"}
    undeclared_parents = []
    for asset in blueprint.assets:
        if asset.path.startswith("$") or "/" not in asset.path:
            continue
        parent = str(Path(asset.path).parent).replace("\\", "/")
        if parent not in declared_directories:
            undeclared_parents.append(f"{asset.path} -> {parent}")
    assert undeclared_parents == []


def test_blueprint_diff_calls_out_product_surface_changes() -> None:
    previous = {
        "assets": [
            {
                "id": "readme",
                "path": "README.md",
                "ownership": "tool-guidance",
                "condition": "always",
            },
            {
                "id": "outline",
                "path": "paper/outline.md",
                "ownership": "editable-starter",
                "condition": "paper",
            },
            {
                "id": "removed",
                "path": "old.md",
                "ownership": "tool-guidance",
                "condition": "always",
            },
        ]
    }
    current = {
        "assets": [
            {
                "id": "readme",
                "path": "GUIDE.md",
                "ownership": "editable-starter",
                "condition": "always",
            },
            {
                "id": "outline",
                "path": "paper/outline.md",
                "ownership": "editable-starter",
                "condition": "always",
            },
            {"id": "added", "path": "new.md", "ownership": "tool-guidance", "condition": "always"},
        ]
    }

    assert diff_blueprints(previous, current) == {
        "added": ["new.md"],
        "removed": ["old.md"],
        "renamed": ["README.md -> GUIDE.md"],
        "ownership_changed": ["GUIDE.md: tool-guidance -> editable-starter"],
        "condition_changed": ["paper/outline.md: paper -> always"],
    }
