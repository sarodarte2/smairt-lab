# Fix what the walk found, with regression tests

Type: task
Status: resolved
Blocked by: 07

## Question

Work the friction inventory from
[the adversarial walk](07-adversarial-friction-walk.md) into fixes, each with a
regression test that encodes the real failure — not an imagined one.

This ticket cannot be scoped until 07 reports; its size is whatever the walk
found. When it is picked up, first **triage the inventory**:

- **Fix now** — crashes, wrong results, and any message the floor audience could
  not recover from. These are the ticket.
- **Fix later** — real but survivable roughness. Graduate to its own ticket or
  to the map's Not yet specified; do not silently carry it.
- **Working as designed** — record why, in the resolution. An entry dismissed
  without a reason will be rediscovered by the next walk.

Standing requirements:

- Every fix lands with a test in the matching `tests/test_*.py` file, named for
  the failure it prevents.
- Error messages are held to the floor audience's standard: say what went wrong,
  in what file or argument, and what to do next. `cli.py`'s `_fail` helper and
  the `_HOOK_OUTSIDE_PROJECT_MESSAGE` constant are the shape to follow — the
  latter is already an example of an error that teaches rather than reports.
- No raw traceback should reach a user for any input the walk exercised.
- `uv run pytest`, `uv run ruff check .`, `uv run mypy src tests` green.

If the walk surfaces something that is a *design* gap rather than a defect —
a convention that does not exist rather than one that misbehaves — do not fix it
here. Raise it as a new decision ticket on the map.

## Answer

All 13 findings triaged and accounted for: **8 defects fixed, 5 design gaps left
alone** (they need decisions, not patches — see below). 264 tests, up from 244;
ruff, mypy strict, and pytest clean.

| # | Defect | Fix |
|---|---|---|
| C-1 | Malformed YAML *inside* a well-formed block crashed `check`/`status`/`index` | `frontmatter.parse()` wraps `yaml.YAMLError` into `FrontmatterError` |
| C-2 | A README with no frontmatter crashed `status`/`index` but not `check` | `index.scan_units()` skips it, matching `status` and `check` |
| C-3 | `write_once()` let raw `OSError` escape (long name, read-only parent, `--path` at a file) | new `fsutil.WriteError`, wired into `new`, `adopt`, `unit new`, `data new` |
| W-1 | An absolute `paths:`/`--ref` silently passed if it existed anywhere on the machine | `_pointer_resolves` and `_prompted_by_resolves` reject absolute targets |
| W-2 | `--hpc "https://..."` silently recorded `host: "https"` | rejected, with a message pointing at `--url` |
| M-1 | A name slugifying to nothing failed silently, surfacing only on a later collision | `text.has_usable_characters()`; warned at first use |
| M-2 | `SMAIRT010` gave the same message for a *renamed* heading as an empty one | distinguishes "no such heading" from "heading present, body empty" |

**The exit-code contract was broken and is now restored.** Before: a crash in
`run_checks` made `hook report` exit 1 — breaking its documented "always exits 0"
— and `hook gate` exit 1 rather than its documented 0/2. Verified fixed: `report`
exits 0, `gate` exits 2 on real findings.

### Hardening added on review

Removing the crash causes restored the contract *contingently* — it would break
again on the next internal bug. `report`'s "always 0" and `gate`'s "2 means
findings exist" are promises the README and every generated hook config depend
on, so they cannot hold only while smairt is bug-free. `hook` now catches an
unexpected failure from `run_checks` and says plainly that it is a smairt bug
rather than a problem with the researcher's project: `report` keeps its promise
and exits 0; `gate` exits **1, never 2**, for the same reason
`_HOOK_OUTSIDE_PROJECT_MESSAGE` does — 2 must keep meaning "findings exist", and
blocking every edit in a session because smairt itself broke would wedge the
researcher out of their own work with no way to proceed. Regression test added.

### The incomplete fix caught mid-review

`WriteError` was initially caught only in `new`, leaving `adopt`, `unit new`, and
`data new` still able to emit the exact traceback it had just fixed. Completed.

### Agent's own extension, accepted

It applied the absolute-path guard to `_prompted_by_resolves` (SMAIRT008) as well
as `_pointer_resolves` (SMAIRT002), with its own regression test — same
`pathlib` gotcha (`base / target` discards `base` when `target` is absolute),
same fix. The inventory flagged this bug class as applying in principle to every
such call site; acting on that was right.

### Design gaps left for decisions, not patches

`smairt.yaml` has no validation of its own; README-less unit folders are
invisible to every command; nested SMAIRT projects aren't flagged at creation;
`prompted_by:` cycles aren't *detected* (though confirmed not to hang); `--ref`
isn't validated at creation though `--from`'s help promises validation. Each is a
missing convention rather than a misbehaviour. Recorded in Not yet specified.
