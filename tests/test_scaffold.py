"""Tests for the scaffold blueprint (src/smairt/scaffold.py).

Covers loading and validating the checked-in blueprint YAML, and
diff_blueprints()'s added/removed/renamed/ownership-changed comparison.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from smairt.project import Harness, create_project
from smairt.scaffold import diff_blueprints, load_blueprint


def test_scaffold_blueprint_declares_the_day_one_assets() -> None:
    blueprint = load_blueprint()

    assert blueprint.blueprint_version == 2
    assert blueprint.assets  # WP0 left this empty; WP1 repopulates it.


def test_every_always_condition_asset_is_produced_by_smairt_new(tmp_path: Path) -> None:
    """The blueprint is a review manifest, not a render source (see scaffold.py). This
    test is what keeps it coherent with the actual renderer in project.py: every path
    the blueprint declares with condition "always" must exist after `smairt new`, and
    every path `smairt new` actually writes must be declared."""
    blueprint = load_blueprint()
    always_paths = {asset.path for asset in blueprint.assets if asset.condition == "always"}

    root = tmp_path / "project"
    create_project(
        root,
        name="Blueprint Check",
        researcher="Ada Lovelace",
        description="Exercises blueprint/renderer coherence.",
        harness=Harness.claude_code,
        hpc=False,
        paper=False,
        created=date(2026, 1, 1),
        scaffold_version="0.0.0-test",
    )
    produced_paths = {str(path.relative_to(root)) for path in root.rglob("*") if path != root}

    assert always_paths <= produced_paths
    # Every produced top-level scaffold path is declared somewhere in the manifest.
    assert produced_paths <= always_paths


def test_hpc_condition_assets_are_produced_only_when_opted_in(tmp_path: Path) -> None:
    blueprint = load_blueprint()
    hpc_paths = {asset.path for asset in blueprint.assets if asset.condition == "hpc"}
    assert hpc_paths  # the manifest declares at least the hpc opt-in assets

    root = tmp_path / "project"
    create_project(
        root,
        name="HPC Check",
        researcher="Ada Lovelace",
        description="Exercises the hpc opt-in.",
        harness=Harness.claude_code,
        hpc=True,
        paper=False,
        created=date(2026, 1, 1),
        scaffold_version="0.0.0-test",
    )
    produced_paths = {str(path.relative_to(root)) for path in root.rglob("*") if path != root}

    assert hpc_paths <= produced_paths


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
