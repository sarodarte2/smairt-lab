# Close the five design gaps from the friction walk

Type: task
Status: resolved

## Question

The [friction walk](07-adversarial-friction-walk.md) found five gaps that were
deliberately not patched by [ticket 08](08-fix-the-friction.md) because each is a
missing convention rather than a misbehaviour. All five are now decided. Evidence
and reproductions: [the inventory](../research/07-friction-inventory.md).

### DG-1 — `smairt.yaml` is never validated → **fail fast AND a check rule**

A corrupt `smairt.yaml` is silently ignored: `check` and `status` both report a
healthy project and exit 0. `check.py:_adoption_known_folders` swallows it with
`except yaml.YAMLError: return frozenset()`. Every unit README gets `SMAIRT001`
coverage; the project's own identity file gets none.

Worse, `connect.py` disagrees with itself: `read_strict_hooks()` silently falls
back to `False` on a YAML error — **so a researcher who set `strict_hooks: true`
and later broke the file silently loses their gate hook** — while
`_record_harness()` warns on the identical failure.

Do both: unparseable YAML fails fast at project-root resolution, so every command
gives the same error; a file that parses but is missing or has wrong required
fields becomes a new check rule. Then apply ONE degrade policy across
`check.py` and `connect.py` instead of per-call-site choices.

**The researcher must be able to repair the file from the message alone.** This
is a hard requirement, not a nicety — `smairt.yaml` is hand-edited and most
researchers have never opened it. The message must:
1. name the file and what is wrong, with a line number where YAML gives one —
   never a traceback;
2. for a parses-but-invalid file, name the missing or wrong field specifically
   ("no `name:` field"), not "validation failed";
3. **print what a correct file looks like.** It is about eight lines; showing the
   expected shape lets someone repair it by eye with no docs lookup and no
   second command.

Verify by breaking a real `smairt.yaml` several ways — bad indent, stray quote,
deleted `name:`, empty file, a YAML list where a mapping belongs — and reading
each message as someone who has never seen the file before.

### DG-2 — a unit folder with no README is invisible → **warning**

`mkdir experiments/2026-08-20_thing` with files inside: `check` reports no errors,
`status` no warnings, `index` silently excludes it. `scan_units()`'s gate is
`entry.is_dir() and readme.is_file()`; anything else is skipped with no rule at
all. A researcher who forgot or deleted a README gets no signal their work is
untracked.

New **warning** rule — the same severity as `SMAIRT006` structure drift, which is
the same class of problem. Not an error (too harsh for a folder just created),
not a suggestion (too quiet for work silently going untracked). The message must
say how to fix it: `smairt unit new` is the only supported way to create a unit,
so the folder is either a mistake to remove or work that needs a real unit.

### DG-3 — nested projects are silently allowed → **warn at creation AND sharpen SMAIRT006**

`smairt new` inside an existing project creates it with no comment. Because every
command walks up to the nearest `smairt.yaml`, the inner project shadows the
outer one. The outer project catches it later only as generic `SMAIRT006`, which
names the folder but not the situation.

Two changes:
- **Warn at creation**, still create. Name the situation plainly and say which
  project wins for commands run inside it. **The precedent is in the same
  command**: `smairt new`'s Git handling already detects an outer repository and
  explains itself in plain language ("this project sits inside an existing Git
  repository, so Git was left alone rather than nesting a second one"). Match
  that voice.
- **Sharpen `SMAIRT006`** so that when the unknown top-level folder is itself a
  SMAIRT project (it contains a `smairt.yaml`), the message says so instead of
  leaving the researcher to work out the cause.

### DG-4 — `prompted_by:` cycles are not detected → **error**

`prompted_by:` records that one question came from another. A cycle is a loop —
A came from B, B came from C, C came from A — which cannot happen in real work
and is only reachable by hand-editing frontmatter.

Confirmed by the walk: **nothing hangs or crashes** (verified under a hard 15s
timeout), so ticket 10's cycle guard holds and must not be touched. But
`SMAIRT008` only checks that each link *resolves*, not that the graph is acyclic,
so `check` reports a cyclic project completely clean — and `INDEX.md` silently
stops nesting the affected unit, with no message that anything was dropped. The
tool already knows the graph is broken and says nothing.

New **error** rule naming the units in the loop. Because it needs hand-editing to
occur, it will never fire on normal work.

### DG-5 — `--ref` isn't validated at creation → **validate it**

`smairt unit new --help` states for `--from`: *"Validated to exist at creation."*
No such promise for `--ref`, and a `--ref` to a nonexistent, absolute, or
`..`-escaping path is accepted immediately. The walk found this by surprise
rather than by checking a stated promise.

Validate `--ref` at creation exactly as `--from` is. `--ref` points at
*pre-existing* code by definition, so there is no legitimate forward reference.
Ticket 08 already made an absolute `paths:` fail `check`; this moves the failure
earlier, to where the researcher can still fix it easily.

## Definition of done

New rules take the next free finding ids (`SMAIRT011`+), never renumbering an
existing one, each with a row in `check.py`'s docstring table. Every new message
names the fix. Regression tests for all five. `README.md`/`docs/REFERENCE.md`
updated where behaviour changed. ruff, mypy strict, and pytest green; a fresh
project still passes `smairt check` with zero findings.

## Answer

All five closed. Three new rules — `SMAIRT011` (project identity), `SMAIRT012`
(README-less folder, warning), `SMAIRT013` (`prompted_by:` cycle, error) — plus
fail-fast config parsing, a nesting warning at creation, a sharpened `SMAIRT006`,
and `--ref` validation. 315 tests, up from 264. ruff, mypy strict, pytest green;
a fresh project still passes `smairt check` with zero findings; the cycle case
still does not hang under a hard 15s timeout.

**The repair requirement is met.** A broken `smairt.yaml` now produces, from every
command:

```
smairt check: .../smairt.yaml is not valid YAML (mapping values are not allowed here, line 2).

A correct smairt.yaml looks like this:

schema_version: 2
scaffold_version: 0.4.0
name: My Project
...
```

Named file, line number, no traceback, and the correct shape to compare against —
repairable by eye with no docs lookup. The example is rendered by
`render_identity` itself, so it cannot drift from the real schema.

### Two corrections on review

1. **A `../`-escaping relative pointer still passed `check` clean.** The agent
   flagged this honestly as outside DG-5's scope (which covers `--ref` at
   *creation*), and it was right that creation is now guarded — but a
   hand-edited `paths:` with enough `../` to reach the real `/etc/hosts`
   **passed with zero findings**, verified. That is the same defect ticket 08
   fixed for absolute paths, in its other spelling: absolute targets *look*
   like escapes and were caught, `../` ones do not and were not. Fixed in
   `_pointer_resolves` via a new `_is_inside` helper comparing resolved paths,
   with a regression test.

2. **The DG-1 policy was made consistent in the wrong direction.** The agent
   deleted `_record_harness`'s existing warning so all three readers were
   silent. But `smairt connect codex` on an invalid `smairt.yaml` then listed
   every wiring file it wrote, exited 0, and **silently failed to record the
   harness** — the researcher learning it only from a later `check`. The policy
   now splits on **reads versus writes**, which is principled rather than
   per-call-site: a *read* falls back silently to a documented safe default
   (`read_strict_hooks` → non-strict, `_adoption_known_folders` → none), because
   nothing the researcher asked for went missing; a *write* that cannot happen
   always warns, because they asked for it and silence lets a command report
   success while the change never landed. Documented in `check.py`'s "Judgment
   calls"; test updated to assert the warning.

### Also verified

`--ref` now rejects nonexistent, absolute, and `../`-escaping paths at creation,
and `--help` promises validation for both `--from` and `--ref`. The nesting
warning matches the voice of the Git-nesting message in the same command.
`index._ordered_for_index`'s cycle guard was not touched, as required.
