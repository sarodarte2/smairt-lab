"""Tests for ``smairt new`` (src/smairt/project.py): the day-one scaffold.

Covers the full set of files/folders create_project() writes, the
write-once refusal on a second run, and the rendered content of
AGENTS.md/STATUS.md/smairt.yaml.
"""

from __future__ import annotations

import shutil
import subprocess
from datetime import date
from pathlib import Path

import pytest
import yaml

from smairt.fsutil import PathExistsError
from smairt.project import (
    Harness,
    ProjectConfigError,
    create_project,
    example_smairt_yaml,
    find_enclosing_project,
    find_project_root,
    init_git,
    read_project_config,
)

GOLDEN_FIXTURE = Path(__file__).parent / "fixtures" / "golden"

GIT_AVAILABLE = shutil.which("git") is not None

TEN_ITEMS = {
    "smairt.yaml",
    "STATUS.md",
    "AGENTS.md",
    "CLAUDE.md",
    ".gitignore",
    "background",
    "data",
    "scripts",
    "experiments",
    "results",
}


def _create(tmp_path: Path, **overrides: object) -> Path:
    root = tmp_path / "project"
    defaults: dict[str, object] = dict(
        name="Test Project",
        researcher="Ada Lovelace",
        description="A project used to exercise smairt new.",
        harness=Harness.claude_code,
        hpc=False,
        paper=False,
        created=date(2026, 1, 1),
        scaffold_version="0.0.0-test",
    )
    defaults.update(overrides)
    create_project(root, **defaults)  # type: ignore[arg-type]
    return root


def test_default_project_has_exactly_the_ten_day_one_items(tmp_path: Path) -> None:
    root = _create(tmp_path)

    assert {entry.name for entry in root.iterdir()} == TEN_ITEMS


def test_smairt_yaml_matches_part_ii_schema(tmp_path: Path) -> None:
    root = _create(tmp_path, harness=Harness.codex)

    config = yaml.safe_load((root / "smairt.yaml").read_text())

    assert config == {
        "schema_version": 2,
        "scaffold_version": "0.0.0-test",
        "name": "Test Project",
        "researcher": "Ada Lovelace",
        "description": "A project used to exercise smairt new.",
        "created": date(2026, 1, 1),
        "harnesses": ["codex"],
        "settings": {"strict_hooks": False},
    }


def test_harness_none_records_an_empty_harness_list(tmp_path: Path) -> None:
    root = _create(tmp_path, harness=Harness.none)

    config = yaml.safe_load((root / "smairt.yaml").read_text())

    assert config["harnesses"] == []


def test_generation_never_overwrites_an_existing_file(tmp_path: Path) -> None:
    root = tmp_path / "project"
    _create(tmp_path)

    with pytest.raises(PathExistsError):
        create_project(
            root,
            name="Test Project",
            researcher="Ada Lovelace",
            description="second call",
            created=date(2026, 1, 1),
        )
    # The original file must be untouched by the failed second call.
    assert "second call" not in (root / "STATUS.md").read_text()


def test_empty_description_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        _create(tmp_path, description="   ")


def test_empty_researcher_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        _create(tmp_path, researcher="  ")


def test_hpc_opt_in_adds_hpc_folder_with_readme_and_template(tmp_path: Path) -> None:
    root = _create(tmp_path, hpc=True)

    assert (root / "hpc" / "README.md").is_file()
    template = (root / "hpc" / "submit.slurm.example").read_text()
    assert "#SBATCH" in template


def test_hpc_opt_out_by_default_produces_no_hpc_folder(tmp_path: Path) -> None:
    root = _create(tmp_path)

    assert not (root / "hpc").exists()


def test_paper_opt_in_adds_a_status_open_question_and_nothing_else(tmp_path: Path) -> None:
    with_paper = _create(tmp_path / "with_paper", hpc=False, paper=True)
    without_paper = _create(tmp_path / "without_paper", hpc=False, paper=False)

    with_status = (with_paper / "STATUS.md").read_text()
    without_status = (without_paper / "STATUS.md").read_text()

    assert "paper" in with_status.lower()
    assert "paper" not in without_status.lower()
    # No other file changes: the opt-in only touches STATUS.md's open questions.
    with_files = {p.relative_to(with_paper) for p in with_paper.rglob("*") if p.is_file()}
    without_files = {p.relative_to(without_paper) for p in without_paper.rglob("*") if p.is_file()}
    assert with_files == without_files


def test_agents_md_is_under_the_120_line_budget(tmp_path: Path) -> None:
    root = _create(tmp_path)

    agents_lines = len((root / "AGENTS.md").read_text().splitlines())

    assert agents_lines <= 120, f"AGENTS.md is {agents_lines} lines"


def test_other_generated_day_one_prose_is_under_the_150_line_budget(tmp_path: Path) -> None:
    root = _create(tmp_path)

    markdown_files = sorted(p for p in root.rglob("*.md") if p.name != "AGENTS.md")
    total_lines = sum(len(path.read_text().splitlines()) for path in markdown_files)

    assert total_lines < 150, f"{total_lines} lines across {[str(p) for p in markdown_files]}"


def test_matches_golden_fixture_byte_for_byte(tmp_path: Path) -> None:
    root = tmp_path / "golden"
    create_project(
        root,
        name="Golden Project",
        researcher="Ada Lovelace",
        description="A golden fixture project used to catch scaffold drift.",
        harness=Harness.claude_code,
        hpc=False,
        paper=False,
        created=date(2026, 1, 1),
        scaffold_version="0.0.0-golden",
    )

    generated = _read_tree(root)
    golden = _read_tree(GOLDEN_FIXTURE)

    assert generated == golden


def _read_tree(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=False
    )


@pytest.mark.skipif(not GIT_AVAILABLE, reason="git is not installed")
def test_init_git_creates_a_repo_and_stages_the_scaffold_without_committing(
    tmp_path: Path,
) -> None:
    root = _create(tmp_path)

    result = init_git(root)

    assert result.outcome == "initialized"
    assert (root / ".git").is_dir()
    staged = _git(root, "status", "--porcelain").stdout
    # Every scaffold file shows up staged ("A ", not "??" or "M").
    assert "A  smairt.yaml" in staged
    assert "A  AGENTS.md" in staged
    # Nothing was committed -- `git log` has nothing to show yet.
    log = _git(root, "log")
    assert log.returncode != 0


@pytest.mark.skipif(not GIT_AVAILABLE, reason="git is not installed")
def test_init_git_on_an_already_initialized_repo_is_a_noop(tmp_path: Path) -> None:
    root = _create(tmp_path)
    _git(root, "init")

    result = init_git(root)

    assert result.outcome == "skipped"
    # The no-op path never runs `git add`, so nothing is staged yet.
    staged = _git(root, "status", "--porcelain").stdout
    assert "A  smairt.yaml" not in staged


@pytest.mark.skipif(not GIT_AVAILABLE, reason="git is not installed")
def test_init_git_inside_an_existing_work_tree_does_not_nest_a_second_repo(
    tmp_path: Path,
) -> None:
    # Reproduces the "lab monorepo" / "whole project tree is one repo" case:
    # the OUTER directory is already a Git work tree before `smairt new`
    # ever creates the project folder underneath it, so the project folder
    # itself never has its own `.git` at the time init_git runs.
    outer = tmp_path / "outer"
    outer.mkdir()
    _git(outer, "init")

    root = outer / "project"
    root.mkdir()
    # A fresh project directory the day-one scaffold hasn't populated yet is
    # enough to prove the point -- init_git only needs `root` to exist.

    result = init_git(root)

    assert result.outcome == "skipped"
    assert "existing Git repository" in result.message
    assert not (root / ".git").exists()
    # The outer repo is untouched too -- nothing was staged into it.
    outer_status = _git(outer, "status", "--porcelain").stdout
    assert outer_status.strip() == ""


@pytest.mark.skipif(not GIT_AVAILABLE, reason="git is not installed")
def test_gitignore_excludes_dataset_contents_but_tracks_dataset_readmes(
    tmp_path: Path,
) -> None:
    """Verify the .gitignore patterns for real, not just by inspection.

    ``data/**`` excludes everything under data/ (including subfolders),
    then ``!data/README.md`` / ``!data/*/`` / ``!data/*/README.md``
    re-include the top-level README, the dataset subfolders themselves
    (git's rule: a file can't be re-included unless its parent directory
    is re-included first), and each dataset's own README -- but not any
    other file a dataset folder holds, like the raw data itself.
    """
    root = _create(tmp_path)
    _git(root, "init")

    dataset_dir = root / "data" / "some_dataset"
    dataset_dir.mkdir(parents=True)
    (dataset_dir / "README.md").write_text("# some_dataset\n\nProvenance goes here.\n")
    (dataset_dir / "raw.csv").write_text("col_a,col_b\n1,2\n3,4\n")

    _git(root, "add", "-A")

    tracked = set(_git(root, "ls-files").stdout.splitlines())
    assert "data/README.md" in tracked
    assert "data/some_dataset/README.md" in tracked
    assert "data/some_dataset/raw.csv" not in tracked


# --- DG-1: smairt.yaml fail-fast + read_project_config -------------------------


def test_find_project_root_returns_none_outside_any_project(tmp_path: Path) -> None:
    assert find_project_root(tmp_path) is None


def test_find_project_root_finds_the_root_from_a_subdirectory(tmp_path: Path) -> None:
    root = _create(tmp_path)
    deep = root / "experiments" / "nested"
    deep.mkdir(parents=True)

    assert find_project_root(deep) == root


def test_find_project_root_raises_on_a_yaml_syntax_error(tmp_path: Path) -> None:
    # DG-1's fail-fast half: a genuine YAML syntax error (not just a schema
    # problem) must be caught the moment the project root is resolved, the
    # same point every `smairt` command already goes through, so every
    # command gives the same message instead of each discovering the
    # breakage its own way (or a raw traceback) several calls later.
    root = _create(tmp_path)
    (root / "smairt.yaml").write_text("name: X\n  researcher: bad indent\n", encoding="utf-8")

    with pytest.raises(ProjectConfigError) as excinfo:
        find_project_root(root)

    message = str(excinfo.value)
    assert "smairt.yaml" in message
    assert "not valid YAML" in message
    assert "line 2" in message
    # The hard requirement: showing the correct shape, not just naming the problem.
    assert "A correct smairt.yaml looks like this" in message
    assert "name: My Project" in message


def test_find_project_root_raises_on_a_stray_quote(tmp_path: Path) -> None:
    root = _create(tmp_path)
    (root / "smairt.yaml").write_text('name: "Unterminated\nresearcher: X\n', encoding="utf-8")

    with pytest.raises(ProjectConfigError) as excinfo:
        find_project_root(root)

    message = str(excinfo.value)
    assert "not valid YAML" in message
    assert "line" in message


def test_find_project_root_does_not_raise_on_a_schema_only_problem(tmp_path: Path) -> None:
    # A file that PARSES but is missing a required field (or is empty, or is
    # a list) is NOT this function's job -- that is rule SMAIRT011, checked
    # only once the project root is already known to be resolvable. See
    # tests/test_check.py for the SMAIRT011 coverage of these cases.
    root = _create(tmp_path)
    (root / "smairt.yaml").write_text("", encoding="utf-8")

    assert find_project_root(root) == root


def test_read_project_config_reports_missing_file(tmp_path: Path) -> None:
    result = read_project_config(tmp_path)

    assert result.data is None
    assert result.problem is not None
    assert "missing" in result.problem


def test_read_project_config_reports_empty_file(tmp_path: Path) -> None:
    (tmp_path / "smairt.yaml").write_text("", encoding="utf-8")

    result = read_project_config(tmp_path)

    assert result.data is None
    assert result.problem is not None
    assert "empty" in result.problem


def test_read_project_config_reports_a_yaml_list_as_not_a_mapping(tmp_path: Path) -> None:
    (tmp_path / "smairt.yaml").write_text("- a\n- b\n", encoding="utf-8")

    result = read_project_config(tmp_path)

    assert result.data is None
    assert result.problem is not None
    assert "mapping" in result.problem


def test_read_project_config_reports_a_syntax_error_defensively(tmp_path: Path) -> None:
    # Defense in depth: read_project_config never raises even on a genuine
    # YAML syntax error, since a caller could reach it without having gone
    # through find_project_root's fail-fast first (a test, or a future
    # direct library caller).
    (tmp_path / "smairt.yaml").write_text("name: X\n  researcher: bad indent\n", encoding="utf-8")

    result = read_project_config(tmp_path)

    assert result.data is None
    assert result.problem is not None
    assert "not valid YAML" in result.problem


def test_read_project_config_returns_data_for_a_normal_project(tmp_path: Path) -> None:
    root = _create(tmp_path)

    result = read_project_config(root)

    assert result.problem is None
    assert result.data is not None
    assert result.data["name"] == "Test Project"


def test_example_smairt_yaml_is_itself_a_valid_mapping_with_the_identity_fields() -> None:
    example = example_smairt_yaml()
    parsed = yaml.safe_load(example)

    assert isinstance(parsed, dict)
    assert parsed["name"] and parsed["researcher"] and parsed["description"]


# --- DG-3: nesting detection (find_enclosing_project) ---------------------------


def test_find_enclosing_project_returns_none_outside_any_project(tmp_path: Path) -> None:
    assert find_enclosing_project(tmp_path) is None


def test_find_enclosing_project_finds_an_outer_project(tmp_path: Path) -> None:
    outer = _create(tmp_path)
    inner_parent = outer / "some_subdir"
    inner_parent.mkdir()

    assert find_enclosing_project(inner_parent) == outer


def test_find_enclosing_project_does_not_raise_on_a_broken_outer_config(tmp_path: Path) -> None:
    # A broken smairt.yaml in the OUTER (unrelated, from this call's point of
    # view) project is that project's own problem, not a reason to refuse
    # resolving the nesting check for a new, different project.
    outer = _create(tmp_path)
    (outer / "smairt.yaml").write_text("name: X\n  researcher: bad indent\n", encoding="utf-8")
    inner_parent = outer / "some_subdir"
    inner_parent.mkdir()

    assert find_enclosing_project(inner_parent) == outer
