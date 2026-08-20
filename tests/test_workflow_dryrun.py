"""WP5 acceptance: the dry-run workflow (spec WP5 acceptance criterion).

Follows only the command sequence AGENTS.md + the skills prescribe — the same
one a fresh assistant would run in an empty project — end to end:

    smairt new -> smairt status (smairt-orient) -> smairt unit new question
    (smairt-new-question) -> [a run happens, log captured] -> edit frontmatter
    status+verdict, edit STATUS.md (smairt-close-question) -> smairt check

This is what makes the loop's coherence falsifiable rather than merely
plausible-sounding prose (repo testing tradition: every rule and every loop
step gets a test that would fail if the step stopped working).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

from smairt import frontmatter
from smairt.cli import app
from smairt.text import slugify

runner = CliRunner()


def test_dry_run_workflow_from_empty_project_to_a_clean_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 1. smairt new — an empty project, no harness wiring to keep this test
    #    focused on the research loop rather than hook installation.
    new_result = runner.invoke(
        app,
        [
            "new",
            "--name",
            "Dry Run Project",
            "--researcher",
            "Ada Lovelace",
            "--description",
            "Exercises the WP5 dry-run workflow end to end.",
            "--path",
            str(tmp_path),
            "--harness",
            "none",
            "--no-hpc",
            "--no-paper",
        ],
        input="",
    )
    assert new_result.exit_code == 0, new_result.output
    root = tmp_path / "dry_run_project"
    assert (root / "AGENTS.md").is_file()
    monkeypatch.chdir(root)

    # 2. smairt-orient — run `smairt status` to see where a fresh project
    #    stands before doing any work. Zero units yet; nothing to fix.
    orient_result = runner.invoke(app, ["status"])
    assert orient_result.exit_code == 0, orient_result.output
    assert "No open questions" in orient_result.output

    # 3. smairt-new-question — sharpen the hypothesis, then let `smairt unit
    #    new` do the mechanics. Never hand-create the folder.
    title = "Does excluding replicate 3 change the results"
    hypothesis = "Excluding replicate 3 sharpens the separation between groups."
    new_question_result = runner.invoke(
        app,
        ["unit", "new", "question", "--title", title, "--hypothesis", hypothesis],
    )
    assert new_question_result.exit_code == 0, new_question_result.output

    slug = slugify(title, fallback="question", sep="-")
    unit_dir = root / "experiments" / f"{date.today().isoformat()}_{slug}"
    assert unit_dir.is_dir()
    fields, body = frontmatter.read(unit_dir / "README.md")
    assert fields["status"] == "open"
    assert fields["hypothesis"] == hypothesis
    assert fields["log"] == f"logs/{slug}.log"

    # The analysis plan is written now too, in the same conversation that
    # sharpened the hypothesis -- before anything runs (smairt-new-question).
    body = body.replace(
        "## Analysis plan\n\n",
        "## Analysis plan\n\nCompare the separation score with and without "
        "replicate 3; call the hypothesis supported if excluding it raises "
        "the score.\n\n",
    )

    # 4. A run happens: one-off probe code stays inside its unit (AGENTS.md's
    #    "own code" case), and the raw log lands where the unit's
    #    frontmatter already points (pre-filled by `smairt unit new`).
    script_path = unit_dir / "probe_replicate3.R"
    script_path.write_text(
        "# Compares separation score with and without replicate 3.\n",
        encoding="utf-8",
    )
    log_path = unit_dir / fields["log"]
    log_path.write_text(
        "replicate_3_excluded: separation_score=0.81\n"
        "replicate_3_included: separation_score=0.62\n",
        encoding="utf-8",
    )

    # 5. smairt-close-question — read the log, write facts and interpretation
    #    into the README body, then set status + verdict together in the
    #    frontmatter (a small script edit, exactly as an assistant would do
    #    it — never touching the raw log itself).
    body = body.replace(
        "## What happened\n\n",
        "## What happened\n\nSeparation score 0.81 with replicate 3 excluded, "
        "0.62 with it included (see logs/{}.log).\n\n".format(slug),
    )
    body = body.replace(
        "## What it means\n\n",
        "## What it means\n\nExcluding replicate 3 raises the separation score, "
        "supporting the hypothesis (logs/{}.log).\n\n".format(slug),
    )
    fields["script"] = "probe_replicate3.R"
    fields["status"] = "supported"
    fields["verdict"] = "Excluding replicate 3 improves separation; hypothesis supported."
    (unit_dir / "README.md").write_text(frontmatter.render(fields) + body, encoding="utf-8")

    # 6. Propose and apply the 3-line STATUS.md update.
    status_path = root / "STATUS.md"
    status_fields, status_body = frontmatter.read(status_path)
    status_fields["updated"] = date.today()
    status_body = status_body.replace(
        "Create the first stage or question with `smairt unit new`.",
        "Follow up: check whether the replicate-3 effect holds on the full cohort.",
    )
    status_body = status_body.replace(
        "## Open questions\n",
        "## Open questions\n- Does the replicate-3 effect hold on the full cohort?\n",
    )
    status_path.write_text(frontmatter.render(status_fields) + status_body, encoding="utf-8")

    # 7. smairt check — the closed unit and the refreshed STATUS.md both pass
    #    with zero findings.
    check_result = runner.invoke(app, ["check"])
    assert check_result.exit_code == 0, check_result.output
    assert "No errors or warnings" in check_result.output

    # And a second `smairt status` confirms the loop closed cleanly end to end.
    final_status = runner.invoke(app, ["status"])
    assert final_status.exit_code == 0, final_status.output
    assert "supported" in final_status.output
