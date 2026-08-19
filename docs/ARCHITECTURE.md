# SMAIRT architecture

A short tour before you open the code. Read this once; after that, each
module's own docstring should be enough to orient.

## What SMAIRT is

A command-line tool a researcher installs (`pip install smairt`) that scaffolds
a disciplined project layout and then keeps checking that the layout stays
disciplined. It never watches or edits a researcher's actual analysis — it
only manages the *structure* around it: folders, README frontmatter, and a
few generated files.

## The three layers

```
Researcher / assistant harness
        |
   smairt <command>          <- src/smairt/cli.py
        |
   one module per command    <- project.py / units.py / check.py / status.py /
        |                        connect.py / adopt.py / index.py
        v
   shared plumbing           <- frontmatter.py / fsutil.py / text.py / models.py
```

1. **`cli.py`** is the only file Typer (the CLI library) touches directly. Every
   function decorated `@app.command()` there is one `smairt` subcommand. It
   parses flags, calls into the matching module below, and prints the result —
   no real logic lives here.
2. **One module per command** does the actual work. Each is documented in its
   own module docstring; the short version:
   - `project.py` — `smairt new`, the day-one scaffold.
   - `units.py` — `smairt unit new`, creating one stage or question folder.
   - `check.py` — `smairt check`, the eight rules that audit a project's state.
   - `status.py` — `smairt status`, orientation (reuses `check.py`'s rules).
   - `connect.py` — `smairt connect`, wiring an assistant harness's hooks.
   - `adopt.py` — `smairt adopt`, wrapping a pre-existing project.
   - `index.py` — `smairt index`, regenerating `results/INDEX.md`.
3. **Shared plumbing** has no command of its own; every module above leans on
   it. `frontmatter.py` reads/writes the `---` YAML block at the top of a
   README. `fsutil.py` holds the two file-writing policies (`write_once` /
   `write_or_warn`) that keep SMAIRT from ever silently clobbering a
   researcher's edits. `text.py` turns titles into folder-safe slugs.
   `models.py` is the `Researcher` identity shape.

## Where generated text lives

Almost every file SMAIRT writes is a plain Python string, formatted and
written directly — there is no template engine. `project.py` holds the
day-one scaffold's text (`_AGENTS_TEMPLATE`, `_GITIGNORE`, the various
`_README` constants); `connect.py` holds one render function per harness
(`_render_claude_settings`, `_render_codex_hooks`, ...); `units.py` builds a
unit README's frontmatter + body inline in `create_stage`/`create_question`.
`results/INDEX.md` is the one exception: it is *derived*, not a skeleton, so
`index.py` regenerates it fresh on every relevant command instead of writing
it once.

## How a finding travels from a rule to the terminal

`smairt check` has eight rules, each a `_check_*` (findings) or `_suggest_*`
(advisory suggestions) function in `check.py`. `run_checks()` loads every unit
once (`_load_units`) and hands that same list to each rule in turn, collecting
everything into one `CheckReport`. `cli.py`'s `check` command calls
`run_checks()`, then either `render_human()` (plain text) or `to_json()`
(machine-readable), and exits with `report.exit_code` — 1 if there are any
findings, 0 otherwise. `smairt status` reuses `run_checks()` directly rather
than re-implementing any of this.

## Adding things

**A new check rule**: write a `_check_*` function in `check.py` following the
existing rules' shape (loop over `units`, append `Finding`s using a rule
constant like `RULE_FRONTMATTER`), give it a new `SMAIRTNNN` id in the module
docstring's table, and call it from `run_checks()`. An advisory-only rule
(never affects the exit code) is a `_suggest_*` function returning
`Suggestion`s instead.

**A new harness for `smairt connect`**: add a value to the `Harness` enum in
`project.py`, write a `_render_<name>_*` function plus a `_connect_<name>`
function in `connect.py` following the existing harnesses' shape, and add it
to the `_HARNESS_HANDLERS` dispatch table at the bottom of that file.

## Tests

One test file per module, named to match (`tests/test_check.py` tests
`check.py`, and so on), plus `tests/fixtures/golden/` — a checked-in example
project that must keep passing `smairt check` clean. `tests/test_workflow_dryrun.py`
runs the whole command sequence end to end, the way a fresh assistant would.
