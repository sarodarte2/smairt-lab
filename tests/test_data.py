"""Tests for ``smairt data`` (src/smairt/data.py): recording where each dataset lives.

Covers the module (create_dataset/add_location/list_locations, the Location
dataclass's own validation) and the CLI (`smairt data new|locate|list`),
following tests/test_units.py for the shape of a module+CLI test file.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

from smairt import frontmatter
from smairt.cli import app
from smairt.data import DataReport, Location, add_location, create_dataset, list_locations, to_json
from smairt.fsutil import PathExistsError
from smairt.project import Harness, create_project

runner = CliRunner()


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    create_project(
        root,
        name="Data Test Project",
        researcher="Ada Lovelace",
        description="Exercises smairt data.",
        harness=Harness.claude_code,
        created=date(2026, 1, 1),
        scaffold_version="0.0.0-test",
    )
    return root


# --- Location --------------------------------------------------------------------


def test_location_rejects_an_unrecognized_kind() -> None:
    with pytest.raises(ValueError):
        Location(kind="cloud", path="s3://bucket/key")


def test_location_rejects_an_empty_path() -> None:
    with pytest.raises(ValueError):
        Location(kind="local", path="   ")


def test_location_hpc_kind_requires_a_host() -> None:
    with pytest.raises(ValueError):
        Location(kind="hpc", path="/scratch/proj/")


def test_location_local_kind_does_not_require_a_host() -> None:
    location = Location(kind="local", path="data/foo/")
    assert location.host is None


# --- create_dataset ----------------------------------------------------------------


def test_create_dataset_writes_a_slugified_folder_with_a_readme(tmp_path: Path) -> None:
    root = _project(tmp_path)

    dataset_dir = create_dataset(root, "TCGA RNAseq!!")

    assert dataset_dir == root / "data" / "tcga_rnaseq"
    assert (dataset_dir / "README.md").is_file()


def test_create_dataset_readme_opens_with_the_dataset_slug_in_frontmatter(
    tmp_path: Path,
) -> None:
    root = _project(tmp_path)

    dataset_dir = create_dataset(root, "TCGA RNA-seq")
    fields, body = frontmatter.read(dataset_dir / "README.md")

    assert fields["dataset"] == "tcga_rna_seq"
    assert "## Provenance" in body


def test_create_dataset_always_records_a_local_location_pointing_at_itself(
    tmp_path: Path,
) -> None:
    root = _project(tmp_path)

    dataset_dir = create_dataset(root, "Reads")
    fields, _body = frontmatter.read(dataset_dir / "README.md")

    assert fields["locations"] == [{"kind": "local", "path": "data/reads/"}]


def test_create_dataset_appends_caller_supplied_locations_after_the_automatic_one(
    tmp_path: Path,
) -> None:
    root = _project(tmp_path)

    dataset_dir = create_dataset(
        root,
        "TCGA RNAseq",
        locations=[
            Location(kind="hpc", host="constance.pnnl.gov", path="/scratch/proj/tcga/"),
            Location(kind="url", path="https://portal.example.org/download", note="source"),
        ],
    )
    fields, _body = frontmatter.read(dataset_dir / "README.md")

    assert fields["locations"] == [
        {"kind": "local", "path": "data/tcga_rnaseq/"},
        {"kind": "hpc", "host": "constance.pnnl.gov", "path": "/scratch/proj/tcga/"},
        {"kind": "url", "path": "https://portal.example.org/download", "note": "source"},
    ]


def test_create_dataset_refuses_a_dataset_that_already_exists(tmp_path: Path) -> None:
    root = _project(tmp_path)
    create_dataset(root, "Reads")

    with pytest.raises(PathExistsError):
        create_dataset(root, "Reads")


# --- add_location --------------------------------------------------------------------


def test_add_location_appends_a_new_location_to_an_existing_dataset(tmp_path: Path) -> None:
    root = _project(tmp_path)
    create_dataset(root, "Reads")

    add_location(root, "Reads", Location(kind="url", path="https://example.org/reads.tar.gz"))
    fields, _body = frontmatter.read(root / "data" / "reads" / "README.md")

    assert {"kind": "url", "path": "https://example.org/reads.tar.gz"} in fields["locations"]


def test_add_location_is_idempotent_for_an_identical_location(tmp_path: Path) -> None:
    root = _project(tmp_path)
    create_dataset(root, "Reads")
    location = Location(kind="hpc", host="constance.pnnl.gov", path="/scratch/reads/")

    add_location(root, "Reads", location)
    add_location(root, "Reads", location)
    fields, _body = frontmatter.read(root / "data" / "reads" / "README.md")

    assert (
        fields["locations"].count(
            {"kind": "hpc", "host": "constance.pnnl.gov", "path": "/scratch/reads/"}
        )
        == 1
    )


def test_add_location_errors_clearly_when_the_dataset_does_not_exist(tmp_path: Path) -> None:
    root = _project(tmp_path)

    with pytest.raises(ValueError, match="no dataset found"):
        add_location(root, "nonexistent", Location(kind="local", path="data/nonexistent/"))


# --- list_locations --------------------------------------------------------------------


def test_list_locations_scans_every_dataset_under_data(tmp_path: Path) -> None:
    root = _project(tmp_path)
    create_dataset(root, "Reads")
    create_dataset(root, "Metadata")

    report = list_locations(root)

    assert {entry.dataset for entry in report.entries} == {"reads", "metadata"}


def test_list_locations_skips_datas_own_readme_not_a_dataset(tmp_path: Path) -> None:
    root = _project(tmp_path)
    create_dataset(root, "Reads")

    report = list_locations(root)

    assert all(entry.dataset != "README.md" for entry in report.entries)
    assert len(report.entries) == 1


def test_list_locations_tolerates_a_hand_written_readme_with_no_frontmatter(
    tmp_path: Path,
) -> None:
    root = _project(tmp_path)
    hand_written = root / "data" / "handmade"
    hand_written.mkdir()
    (hand_written / "README.md").write_text(
        "# Handmade dataset\n\nJust some notes, no YAML block.\n", encoding="utf-8"
    )

    report = list_locations(root)

    assert len(report.entries) == 1
    assert report.entries[0].locations == ()


def test_list_locations_tolerates_a_readme_with_no_locations_field(tmp_path: Path) -> None:
    root = _project(tmp_path)
    handmade = root / "data" / "handmade"
    handmade.mkdir()
    (handmade / "README.md").write_text(
        frontmatter.render({"dataset": "handmade"}) + "\nNo locations here.\n",
        encoding="utf-8",
    )

    report = list_locations(root)

    assert report.entries[0].locations == ()


def test_list_locations_with_no_data_dir_returns_an_empty_report(tmp_path: Path) -> None:
    root = tmp_path / "not_a_project"
    root.mkdir()

    report = list_locations(root)

    assert report == DataReport(entries=())


def test_to_json_shape_lists_dataset_path_and_locations(tmp_path: Path) -> None:
    root = _project(tmp_path)
    create_dataset(root, "Reads")

    payload = to_json(list_locations(root))

    assert payload == {
        "datasets": [
            {
                "dataset": "reads",
                "path": "data/reads",
                "locations": [{"kind": "local", "path": "data/reads/", "host": None, "note": None}],
            }
        ]
    }


# --- CLI: smairt data new -----------------------------------------------------------


def test_cli_data_new_creates_a_dataset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _project(tmp_path)
    monkeypatch.chdir(root)

    result = runner.invoke(app, ["data", "new", "Reads"])

    assert result.exit_code == 0, result.output
    assert (root / "data" / "reads" / "README.md").is_file()


def test_cli_data_new_accepts_repeatable_location_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _project(tmp_path)
    monkeypatch.chdir(root)

    result = runner.invoke(
        app,
        [
            "data",
            "new",
            "TCGA RNAseq",
            "--hpc",
            "constance.pnnl.gov:/scratch/proj/tcga/",
            "--url",
            "https://portal.example.org/download",
            "--local",
            "/mnt/lab-share/tcga/",
            "--note",
            "mirrored nightly",
        ],
    )

    assert result.exit_code == 0, result.output
    fields, _body = frontmatter.read(root / "data" / "tcga_rnaseq" / "README.md")
    kinds = [loc["kind"] for loc in fields["locations"]]
    assert kinds == ["local", "hpc", "url", "local"]
    hpc_entry = next(loc for loc in fields["locations"] if loc["kind"] == "hpc")
    assert hpc_entry["host"] == "constance.pnnl.gov"
    assert hpc_entry["path"] == "/scratch/proj/tcga/"
    assert hpc_entry["note"] == "mirrored nightly"


def test_cli_data_new_hpc_without_a_colon_fails_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _project(tmp_path)
    monkeypatch.chdir(root)

    result = runner.invoke(app, ["data", "new", "Reads", "--hpc", "no-colon-here"])

    assert result.exit_code != 0
    assert "HOST:PATH" in result.output
    assert not (root / "data" / "reads").exists()


def test_cli_data_new_hpc_url_is_rejected_instead_of_corrupting_the_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: `--hpc "https://example.com/data"` used to split cleanly on
    the first ':' (host="https", path="//example.com/data") and pass, silently
    recording a nonsense host -- exactly what a researcher who meant --url
    would produce. It must be rejected the same way the no-colon and
    empty-host cases already are."""
    root = _project(tmp_path)
    monkeypatch.chdir(root)

    result = runner.invoke(app, ["data", "new", "Reads", "--hpc", "https://example.com/data"])

    assert result.exit_code != 0
    assert "--url" in result.output
    assert not (root / "data" / "reads").exists()


def test_cli_data_new_warns_when_name_slugifies_to_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same fallback-announcement fix as `smairt unit new` (see
    test_cli_unit_new_warns_when_title_slugifies_to_nothing), applied to
    `smairt data new`: a symbol-only dataset name used to silently become
    data/dataset/ with no warning."""
    root = _project(tmp_path)
    monkeypatch.chdir(root)

    result = runner.invoke(app, ["data", "new", "???"])

    assert result.exit_code == 0, result.output
    assert "no letters or digits" in result.output + result.stderr
    assert (root / "data" / "dataset").is_dir()


def test_cli_data_new_refuses_outside_a_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["data", "new", "Reads"])

    assert result.exit_code != 0
    assert "not a SMAIRT project" in result.output


# --- CLI: smairt data locate --------------------------------------------------------


def test_cli_data_locate_adds_a_location_to_an_existing_dataset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _project(tmp_path)
    monkeypatch.chdir(root)
    runner.invoke(app, ["data", "new", "Reads"])

    result = runner.invoke(
        app, ["data", "locate", "Reads", "--url", "https://example.org/reads.tar.gz"]
    )

    assert result.exit_code == 0, result.output
    fields, _body = frontmatter.read(root / "data" / "reads" / "README.md")
    assert {"kind": "url", "path": "https://example.org/reads.tar.gz"} in fields["locations"]


def test_cli_data_locate_requires_exactly_one_location_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _project(tmp_path)
    monkeypatch.chdir(root)
    runner.invoke(app, ["data", "new", "Reads"])

    result = runner.invoke(app, ["data", "locate", "Reads"])

    assert result.exit_code != 0
    assert "exactly one of --hpc, --url, --local" in result.output


def test_cli_data_locate_errors_for_a_missing_dataset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _project(tmp_path)
    monkeypatch.chdir(root)

    result = runner.invoke(app, ["data", "locate", "nonexistent", "--local", "data/nonexistent/"])

    assert result.exit_code != 0
    assert "no dataset found" in result.output


# --- CLI: smairt data list ---------------------------------------------------------


def test_cli_data_list_human_output_lists_every_dataset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _project(tmp_path)
    monkeypatch.chdir(root)
    runner.invoke(app, ["data", "new", "Reads"])
    runner.invoke(app, ["data", "new", "Metadata"])

    result = runner.invoke(app, ["data", "list"])

    assert result.exit_code == 0, result.output
    assert "reads" in result.output
    assert "metadata" in result.output


def test_cli_data_list_json_output_shape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _project(tmp_path)
    monkeypatch.chdir(root)
    runner.invoke(app, ["data", "new", "Reads"])

    result = runner.invoke(app, ["data", "list", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["datasets"][0]["dataset"] == "reads"
    assert payload["datasets"][0]["locations"][0]["kind"] == "local"


def test_cli_data_list_with_no_datasets_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _project(tmp_path)
    monkeypatch.chdir(root)

    result = runner.invoke(app, ["data", "list"])

    assert result.exit_code == 0, result.output
    assert "No datasets found" in result.output
