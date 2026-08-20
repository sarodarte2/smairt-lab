# Adversarial friction walk — inventory

Ticket: [07-adversarial-friction-walk.md](../issues/07-adversarial-friction-walk.md).
Consumed by: [08-fix-the-friction.md](../issues/08-fix-the-friction.md) (not yet written
at the time of this walk).

## Method

Installed with `uv tool install --force .` from the `v2-rebuild` checkout into a
throwaway PATH entry (`~/.local/bin/smairt`), then driven entirely from throwaway
directories under `/tmp/smairt-friction-walk/` — never inside the repo checkout. All
work used the installed entry point, never `uv run`.

- **Version tested:** `smairt 0.4.0`
- **Python:** 3.13.13 (host interpreter used by the `uv tool` venv)
- **OS:** macOS (Darwin 27.0.0, arm64)

Every command below is exact and was actually run; output is pasted verbatim (trimmed
only where a traceback repeats a frame already shown in full elsewhere).

## Summary

- **13 findings total:** 3 crash (5 reproductions), 2 wrong-result defects, 3 confusing
  message, 5 design gaps.
- **Nothing leaked outside the project root or to `$HOME`** — verified explicitly for
  `smairt connect` across all six harnesses + `--ci`; the README's project-scoping claim
  holds.
- **The three worst for the audience floor**, in order:
  1. **Malformed YAML inside an otherwise well-formed frontmatter block crashes `check`,
     `status`, and `index`** with a raw `yaml.parser.ParserError` traceback — on the exact
     mistake (an unclosed `[` in a `tags:` list) a scientist hand-editing a README is
     most likely to make. `check` is the one command whose entire job is reporting
     frontmatter problems as findings, and it crashes instead.
  2. **A unit README with no frontmatter block at all crashes `status` and `index`**
     (raw `FrontmatterError` traceback), even though `check` handles the identical file
     gracefully as a `SMAIRT001` finding. A researcher who just saw `check` report this
     cleanly has no reason to expect `status` — the *daily* command — to crash on it.
  3. **An absolute path in `--ref`/`paths:` silently passes `smairt check`** if it
     happens to exist anywhere on the machine (tested with `/etc/hosts`), defeating the
     "resolves from the project root" contract with no warning at all — the one case in
     this walk where the tool doesn't just fail loudly, it succeeds *wrongly*.
- **Crashes with a traceback:** all 3 crash findings below (5 total reproductions across
  `new`, `check`, `status`, `index`). None are handled — every one is a raw Python
  traceback ending in exit code 1, indistinguishable from a normal clean exit by code
  alone.
- **Design gaps** (no fix belongs in ticket 08; each is a missing convention, not a bug):
  DG-1 (`smairt.yaml` has no validation of its own), DG-2 (README-less unit folders are
  invisible), DG-3 (nested projects aren't flagged at creation), DG-4 (`prompted_by`
  cycles aren't detected, only silently dropped from rendering), DG-5 (`--ref` isn't
  validated at creation the way `--from` explicitly promises to be).

---

## CRASH

### C-1 — DEFECT — malformed YAML *inside* a well-formed frontmatter block crashes check, status, and index

**Command:**
```
$ smairt check      # (also: smairt status, smairt index — same traceback, same root cause)
```
Setup: a unit README whose frontmatter opens and closes with `---` correctly, but whose
YAML body is syntactically broken (an unterminated flow sequence):
```yaml
---
kind: question
title: Bad YAML unit
status: open
date: 2026-08-20
hypothesis: 'H'
tags: [unterminated list
---
```

**Expected:** the same treatment `check` gives a *missing* frontmatter block —
a `SMAIRT001` finding naming the file, or at minimum a clean one-line error.

**Actual (all three commands, identical root cause):**
```
╭───────────────────── Traceback (most recent call last) ──────────────────────╮
│ .../site-packages/smairt/cli.py:322 in check                                 │
│ ❱ 322 │   report = check_module.run_checks(root)                             │
│ .../site-packages/smairt/check.py:309 in run_checks                          │
│ ❱ 309 │   units = _load_units(project_root)                                  │
...
│ .../site-packages/smairt/frontmatter.py                                      │
│     data = yaml.safe_load(match.group("yaml"))                               │
╰──────────────────────────────────────────────────────────────────────────────╯
ParserError: while parsing a flow sequence
  in "<unicode string>", line 6, column 7:
    tags: [unterminated list
          ^
expected ',' or ']', but got '<stream end>'
[exit=1]
```
`smairt status` and `smairt index` crash with the identical `ParserError` (different
`cli.py` frame, same `frontmatter.py` origin).

**Root cause:** `frontmatter.parse()` in `src/smairt/frontmatter.py` only wraps the
"file does not open with a well-formed frontmatter block" case (when the `---` regex
fails to match) in `FrontmatterError`. The `yaml.safe_load(match.group("yaml"))` call
right below it is unguarded — any `yaml.YAMLError` from a syntactically broken (but
delimiter-correct) block propagates raw. `check.py:_load_units` only catches
`frontmatter.FrontmatterError`, not `yaml.YAMLError`, so it doesn't matter that `check`
otherwise "handles" bad frontmatter — this path was never routed through that handling.

**Severity:** crash. **Floor recovery:** none — a `ParserError` traceback through four
site-packages frames is not something the audience floor can read, let alone act on.
This is the single highest-value fix candidate in this inventory: one guard clause in
`frontmatter.parse()` (catch `yaml.YAMLError`, re-raise as `FrontmatterError`) would
fix all three commands at once, and would make this case flow through the *already
correct* `SMAIRT001` handling.

### C-2 — DEFECT — a unit README with no frontmatter block at all crashes status and index (but not check)

**Command:**
```
$ smairt status   # also: smairt index
```
Setup: `experiments/01_legacy_stage/README.md` containing plain text with no `---`
block at all (simulating a hand-made folder, or a README a researcher wrote before
learning the convention).

**Expected:** since `smairt check` already handles this file gracefully —

```
Errors:
  SMAIRT001 experiments/01_legacy_stage/README.md: frontmatter block is missing or malformed: file does not open with a well-formed frontmatter block
```

— `status` and `index` (which both scan the same `experiments/` tree) should behave the
same way, or at minimum fail cleanly.

**Actual:**
```
$ smairt status
╭───────────────────── Traceback (most recent call last) ──────────────────────╮
│ .../smairt/cli.py:374 in status                                              │
│ ❱ 374 │   report = status_module.build_status_report(root)                   │
│ .../smairt/status.py:144 in build_status_report                              │
│ ❱ 144 │   index_module.write_index(project_root)                             │
│ .../smairt/index.py:208 in write_index                                       │
│ .../smairt/index.py:77 in scan_units                                         │
│ ❱  77 │   │   fields, _ = frontmatter.read(readme)                           │
│ .../smairt/frontmatter.py:71 in read                                         │
│ ❱  60 │   │   raise FrontmatterError("file does not open with a well-formed  │
│         frontmatter block")                                                  │
╰──────────────────────────────────────────────────────────────────────────────╯
FrontmatterError: file does not open with a well-formed frontmatter block
[exit=1]
```
`smairt index` crashes identically (same `scan_units` call site). Notably,
**`status` silently calls `write_index()` as a side effect** — an undocumented
coupling that means an `index`-only bug also breaks `status`.

**Root cause:** `index.py:scan_units()` calls `frontmatter.read()` with no
`try/except` at all — unlike `check.py:_load_units`, which explicitly catches
`FrontmatterError` and turns it into a `SMAIRT001` finding.

**Severity:** crash. **Floor recovery:** none. Worse than C-1 for trust: the
researcher just watched `check` handle this exact file cleanly, then ran the *other*
everyday command (`status`, described in the map as "the daily surface") and hit a raw
traceback on the same input.

### C-3 — DEFECT — `write_once()` doesn't catch general `OSError`, so `smairt new` crashes on any filesystem-level obstruction (3 reproductions)

Root cause (`src/smairt/fsutil.py`):
```python
def write_once(path: Path, content: str) -> Path:
    if path.exists():
        raise PathExistsError(f"refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)   # <-- unguarded
    path.write_text(content, encoding="utf-8")
```
Only the "already exists" case is handled. Any other `OSError` subclass from `mkdir`/
`write_text` propagates raw. Reproduced three independent ways:

**(a) Name long enough to exceed the filesystem's filename limit:**
```
$ smairt new --name aaaa...(300 a's)... --researcher R --description D --harness none --no-git
╭───────────────────── Traceback (most recent call last) ──────────────────────╮
│ .../smairt/fsutil.py:37 in write_once                                        │
│ ❱ 37 │   if path.exists():                                                   │
╰──────────────────────────────────────────────────────────────────────────────╯
OSError: [Errno 63] File name too long: '/private/tmp/.../aaaa.../smairt.yaml'
[exit=1]
```
(Fails on `path.exists()` itself here — `stat()` errors on an over-length component —
but the same unguarded pattern is what lets `mkdir`/`write_text` crash below.)

**(b) Read-only parent directory:**
```
$ chmod 555 ro_parent
$ smairt new --name blocked --researcher R --description D --harness none --no-git --path ro_parent
╭───────────────────── Traceback (most recent call last) ──────────────────────╮
│ .../smairt/fsutil.py:39 in write_once                                        │
│ ❱ 39 │   path.parent.mkdir(parents=True, exist_ok=True)                      │
╰──────────────────────────────────────────────────────────────────────────────╯
PermissionError: [Errno 13] Permission denied: 'ro_parent/blocked'
[exit=1]
```

**(c) `--path` pointing at an existing regular file, not a directory:**
```
$ touch a_plain_file.txt
$ smairt new --name filepath --researcher R --description D --harness none --no-git --path a_plain_file.txt
╭───────────────────── Traceback (most recent call last) ──────────────────────╮
│ .../smairt/fsutil.py:39 in write_once                                        │
│ ❱ 39 │   path.parent.mkdir(parents=True, exist_ok=True)                      │
╰──────────────────────────────────────────────────────────────────────────────╯
NotADirectoryError: [Errno 20] Not a directory: 'a_plain_file.txt/filepath'
[exit=1]
```

**Expected (all three):** a one-line error naming the problem — e.g. "cannot create
project at `<path>`: permission denied" / "path too long" / "`<path>` is not a
directory" — exit 1.

**Severity:** crash (×3 reproductions, one root cause). **Floor recovery:** none for
any of the three — same "raw traceback, no next step" problem as C-1/C-2. This is a
one-function fix (`write_once` catches `OSError` and re-raises as its own error type)
that would resolve all three at once, same shape as the C-1 fix.

---

## WRONG RESULT (defects — the tool doesn't crash, but silently does the wrong thing)

### W-1 — DEFECT — an absolute path in `--ref`/`paths:` silently escapes the project root and can pass `check` clean

**Command:**
```
$ smairt unit new question --title "Ref absolute" --ref /etc/hosts
Created experiments/2026-08-20_ref-absolute
[exit=0]
$ smairt check
No errors or warnings.          # /etc/hosts genuinely exists on this machine
```
Compare with the same test using a relative path that does *not* exist, which is
correctly caught:
```
$ smairt unit new question --title "Ref to nowhere" --ref does/not/exist.txt
$ smairt check
Errors:
  SMAIRT002 experiments/2026-08-20_ref-to-nowhere/README.md: 'paths: does/not/exist.txt' does not resolve to an existing path
```
and a `..`-escaping relative path, which is also correctly caught:
```
$ smairt unit new question --title "Ref escapes" --ref ../../../etc/hosts
$ smairt check
Errors:
  SMAIRT002 experiments/2026-08-20_ref-escapes/README.md: 'paths: ../../../etc/hosts' does not resolve to an existing path
```
So a `..`-escape to `/etc/hosts` is caught, but a *direct absolute path* to the exact
same file is not.

**Expected:** per `check.py`'s own docstring — "`paths:` names pre-existing paths
relative to the PROJECT ROOT, not the unit folder" — an absolute path should either be
rejected outright, or at minimum still be required to resolve *under the project root*.

**Actual root cause** (`src/smairt/check.py:_pointer_resolves`):
```python
base = project_root if field == "paths" else unit_path
candidate = base / target
if candidate.exists():
    return True
```
In `pathlib`, `Path("/project/root") / "/etc/hosts"` evaluates to `Path("/etc/hosts")`
— an absolute right-hand operand discards the left side entirely. So any absolute
`--ref`/`paths:` value is checked against the *whole filesystem*, not the project. If
that absolute path happens to exist anywhere on the researcher's machine — a very
common accident (pasting a path copied from elsewhere, an editor auto-completing to an
absolute path) — `check` reports it as a healthy, resolved reference.

**Severity:** wrong result. **Floor recovery:** none, because there is nothing to
recover from — the tool reports success. This is the most dangerous class of finding
in the walk: everywhere else the tool is *loud* when something is wrong; here it is
silently, confidently wrong. This also applies in principle to `script:`/`log:`/
`outputs:` (same `base / target` pattern, `unit_path` as base), though those aren't
normally hand-typed with an absolute value the way `--ref` is.

### W-2 — DEFECT — `--hpc` accepts a URL without complaint, silently corrupting the host

**Command:**
```
$ smairt data new "hpc is url" --hpc "https://example.com/data"
Created data/hpc_is_url
[exit=0]
$ smairt data list --json
{
  "dataset": "hpc_is_url",
  "locations": [
    {"kind": "hpc", "path": "//example.com/data", "host": "https", "note": null}
  ]
}
```
Compare with the *correctly rejected* malformed cases right next to it:
```
$ smairt data new "hpc no colon" --hpc "clusterdata"
smairt data new: --hpc expects HOST:PATH (got 'clusterdata', with no ':')
[exit=1]
$ smairt data new "hpc empty host" --hpc ":/data/x"
smairt data new: --hpc expects HOST:PATH, both non-empty (got ':/data/x')
[exit=1]
```

**Expected:** `--hpc` splits on the first colon, and a URL has one — `https://...`
splits into host=`https`, path=`//example.com/data`. This is technically "non-empty on
both sides" so the existing validation passes it, but the result (`host: "https"`) is
never a real hostname and is exactly the kind of value a researcher who meant `--url`
would produce by habit or copy-paste.

**Severity:** wrong result. **Floor recovery:** partial — the record is visible via
`smairt data list`, so a careful researcher who re-reads their own dataset entry might
notice `host: https` looks wrong, but nothing in the tool ever tells them; a
`://` in the host half is a near-certain signal of a `--hpc`/`--url` mix-up.

---

## CONFUSING MESSAGE

### M-1 — DEFECT (message) — a name/title that slugifies to nothing fails with no explanation, across three commands

Names built entirely of emoji, CJK, or punctuation all slugify to the same
fallback (`"project"` for `smairt new`, `"question"`/`"untitled"` shape for
`smairt unit new`, `"dataset"` for `smairt data new`) with **no warning printed on
first use**:
```
$ smairt new --name 实验研究 --researcher R --description D --harness none --no-git
Created /private/tmp/.../work2/project
[exit=0]
```
Two semantically distinct project names silently collapse to the identical folder
name. The collision only surfaces confusingly on the *second* attempt:
```
$ smairt new --name 🎉🎉🎉 --researcher R --description D --harness none --no-git
smairt new: refusing to overwrite existing file: /private/tmp/.../project/smairt.yaml
[exit=1]
```
Reproduced identically for `smairt unit new question --title '???'` /
`'!!!'` → both `experiments/2026-08-20_question`, and `smairt data new '???'` after
`smairt data new ''` → both `data/dataset`.

**Expected:** either the name is rejected up front ("this name doesn't produce a
usable folder name; please include at least one letter or digit"), or the fallback is
at least announced ("name has no usable characters; using `project`") so the
*first* run isn't silently misleading and the *second* run's collision message makes
sense.

**Severity:** confusing message. **Floor recovery:** partial — the display name
(`name: 实验研究`) is correctly preserved verbatim in `smairt.yaml`, so nothing is
lost, but a researcher who runs the same command twice with two different real names
gets an opaque "refusing to overwrite existing file: .../smairt.yaml" with no hint
that both names produced the same folder.

### M-2 — DEFECT (message) — SMAIRT010's "requires non-empty" message is identical whether the section is truly empty or the heading was renamed

**Command:** a closed question whose `## Analysis plan` heading was hand-renamed to
`## Analysis Approach (renamed)`, with real content underneath (`We did the thing.`):
```
$ smairt check
Errors:
  SMAIRT010 .../README.md: status 'supported' requires a non-empty '## Analysis plan' section -- write what you measured and how you judged the result before closing (amend it with '**Amended YYYY-MM-DD:**' if the plan changed after it was written).
```
This is the **exact same message** produced when the section is genuinely empty
(tested independently — identical text, identical error).

**Expected:** since the rule works by exact heading-text match, a researcher who
renamed the heading (plausible: typo, or trying to be more specific) sees a message
that flatly contradicts what's in front of them — they wrote a paragraph, and the tool
insists the section is empty. A message that distinguished "no `## Analysis plan`
heading found" from "heading found but body is empty" would tell them the actual fix
(put the heading text back) rather than send them looking for content they already
wrote.

**Severity:** confusing message. **Floor recovery:** difficult — the message actively
misleads rather than merely under-informing; a scientist re-reading their own file and
being told it's "empty" is a dead end without knowing the heading text itself is
load-bearing.

### M-3 — DESIGN GAP (message) — `--from`'s path-separator rejection shows a doubled, confusing path

```
$ smairt unit new question --title "Path sep from" --hypothesis H6 --from experiments/2026-08-20_baseline-hypothesis
smairt unit new: --from target does not exist: no unit at experiments/experiments/2026-08-20_baseline-hypothesis (check the folder name, or create that unit first)
```
`--from` is documented as "origin unit's folder name," so a researcher typing the full
relative path out of habit gets a doubled `experiments/experiments/...` in the error.
Not dangerous (no traversal, no crash — correctly rejected), just a rougher message
than the other `--from`/`--ref` errors in this walk, most of which are excellent.
**Severity:** merely rough. **Floor recovery:** yes, with a moment's puzzlement — the
path shown is odd but the "check the folder name" suffix still points them the right
direction.

---

## DESIGN GAPS (no bug to fix — a convention doesn't exist yet; candidates for new decision tickets, not for ticket 08)

### DG-1 — `smairt.yaml` has no validation of its own, and error-handling for it is inconsistent across the codebase

A genuinely corrupt `smairt.yaml` (invalid YAML — verified independently with
`yaml.safe_load`, raises `ScannerError`) is **silently ignored** by both `smairt check`
and `smairt status` — both report a perfectly healthy project:
```
$ smairt check
No errors or warnings.
0 error(s), 0 warning(s), 1 suggestion(s).
[exit=0]
```
Traced to `check.py:_adoption_known_folders`, which explicitly does
`except yaml.YAMLError: return frozenset()` — a deliberate degrade-gracefully choice
for *that one reader*, but there is no rule anywhere that instead surfaces "your
`smairt.yaml` is malformed" to the researcher. Every unit README gets this coverage
(`SMAIRT001`); the project's own identity/config file gets none.

The degrade-silently pattern is also inconsistent within `connect.py`: `read_strict_hooks()`
silently falls back to `False` on a YAML error (no warning — a researcher who set
`strict_hooks: true` then broke the file's YAML later would silently lose the
strict-mode gate hook with zero indication), while `_record_harness()` in the same file
*does* warn ("smairt.yaml could not be parsed; harnesses: list left untouched.") on the
identical failure mode. Worth deciding one policy and applying it uniformly, rather
than fixing each call site individually.

### DG-2 — a unit folder under `experiments/` with no `README.md` is completely invisible

```
$ mkdir experiments/2026-08-20_no-readme-unit && echo x > experiments/2026-08-20_no-readme-unit/notes.txt
$ smairt check   # No errors or warnings.
$ smairt status  # No warnings.
$ smairt index   # Updated results/INDEX.md -- folder silently excluded, no mention
```
`index.scan_units()`'s gate is `entry.is_dir() and readme.is_file()` — anything else
under `experiments/` is simply skipped, with no rule (not even a suggestion-level one)
noting "this folder exists but isn't a recognized unit." A scientist who created a
folder and forgot the README (or deleted it) gets no signal their work isn't tracked.

### DG-3 — nesting a new SMAIRT project inside an existing one is silently allowed at creation time

```
$ smairt new --name outer ...   # cwd
$ cd outer && smairt new --name inner ...
Created /private/tmp/.../outer/inner
[exit=0]
```
No warning at creation. The *outer* project's `check`/`status` catches it only
afterward, and only as the generic structure-drift rule:
```
Warnings:
  SMAIRT006 inner: top-level folder is not part of the known scaffold (background/, data/, scripts/, experiments/, results/, hpc/) or this adopted project's known_folders
```
That message is accurate but doesn't name the actual situation ("this is a second
SMAIRT project nested inside this one") — a researcher chasing SMAIRT006 has to
recognize the cause themselves. (For comparison: the default `--git` behavior *does*
detect nesting relative to an outer Git repo and explains itself clearly — see the
"worked well" section — so the precedent for a good message exists elsewhere in the
same command.)

### DG-4 — `prompted_by:` cycles are not detected; a hand-made cycle is silently dropped from `INDEX.md` rendering rather than flagged

Built a 5-level `--from` chain (Q1→Q2→Q3→Q4→Q5), then hand-edited Q1's frontmatter to
add `prompted_by: <Q5's folder>`, closing the loop (Q1→Q2→Q3→Q4→Q5→Q1). Ran `smairt
index`, `smairt check`, `smairt status` each with a hard 15-second timeout via
`subprocess.run(..., timeout=15)`:

```
$ python3 -c "subprocess.run(['smairt','index'], timeout=15, ...)"
Updated results/INDEX.md
[exit=0]
```
**Confirmed: none of the three commands hang or crash** — this is the one place this
walk explicitly went looking for a hang, and didn't find one; worth stating plainly so
ticket 08 doesn't spend effort re-verifying it.

However: `SMAIRT008` only checks that `prompted_by:` resolves to *a real unit*, not
that the graph is acyclic, so `check` reports the cyclic project completely clean.
And `INDEX.md`'s lineage-nesting silently stopped reflecting the new link — Q1 still
renders as a top-level (non-indented) entry despite now carrying `prompted_by:`,
with no message that a cycle was found and something had to give. No rule exists for
"this lineage graph has a cycle" the way one exists for a dangling reference
(`SMAIRT008`'s "does not resolve" case, which has an excellent message — see below).

### DG-5 — `--ref` isn't validated at creation, unlike `--from`, which explicitly promises it is

`smairt unit new --help` states outright, for `--from`: *"Validated to exist at
creation."* No such statement exists for `--ref`, and testing confirms the asymmetry:
`--from` to a nonexistent unit is rejected immediately (see W-1's neighbor test); `--ref`
to a nonexistent, absolute, or `..`-escaping path is accepted immediately and only
caught later (or not at all — see W-1) by `smairt check`. This may be an intentional
design (allow referencing a path that will exist soon), but if so it isn't stated
anywhere the way `--from`'s guarantee is, and the walk found this by surprise, not by
reading a promise and checking it held.

---

## What worked well (ticket 08 must not "fix" these away)

- **Collision safety is completely reliable**: `smairt new`, `smairt unit new`, and
  `smairt data new` never silently overwrite an existing file/unit/dataset — every
  collision produces a clear "refusing to overwrite existing X: `<path>`" naming the
  exact path, across every name-collision scenario tested (see M-1 for the one rough
  edge — the *reason* for the collision, not the collision-safety itself).
- **`smairt adopt`** gives excellent, specific, exit-1 errors for "already a project"
  and "empty directory" (with a direct pointer to `smairt new` in the latter), adopts a
  directory full of unrelated files and even folders that collide with scaffold names
  (`data/`, `experiments/`) without disturbing their pre-existing contents, and leaves a
  dirty Git repo's index/working-tree state completely untouched.
- **`smairt new`'s default Git behavior is genuinely smart**: with neither `--git` nor
  `--no-git`, running inside an *already-existing* outer Git repository correctly
  detects it and skips nested `git init`, explaining itself in plain language:
  *"this project sits inside an existing Git repository, so Git was left alone rather
  than nesting a second one."* Outside any repo, it inits one and stages (never
  commits) the scaffold, exactly as documented.
- **`--hpc` HOST:PATH validation** (no colon, empty host, empty path) produces precise
  messages quoting the exact bad value back — a clean example next to which W-2's gap
  (a URL) stands out.
- **`data locate` on a missing dataset** gives an exact, actionable message:
  *"no dataset found at `data/does_not_exist/README.md` (create it first with
  `smairt data new`)."*
- **`smairt hook report|gate` outside a project** is a standout: a loud, specific
  message that names exactly which global config files to check
  (`~/.claude/settings.json`, `~/.cursor/hooks.json`) and states plainly that wiring
  belongs only inside a project — and it reliably **exits 1, never 2**, exactly as the
  ticket asked to verify. The `report`/`gate` exit-code contract (0 always for report; 2
  only on findings for gate; silent on a clean gate) matches its own documentation in
  every case tested.
- **`smairt connect` is provably project-scoped**: ran all six harnesses plus `--ci`
  and diffed `$HOME`'s changed files before/after — the diff was empty. The README's
  claim holds under direct adversarial testing, not just inspection.
- **`smairt connect` re-runs are fully idempotent** ("Unchanged" reported for every file
  already correct), and **hand-edited generated files are never clobbered** — tested
  against both a hooks config (`.claude/settings.json`) and a skill file
  (`.claude/skills/smairt-orient/SKILL.md`): both were correctly detected as
  researcher-edited and left untouched, with a clear warning
  (*"already exists and differs from the generated version; left untouched (looks
  researcher-edited)"*) rather than being silently overwritten.
- **`strict_hooks: true`** correctly adds a `PreToolUse` gate hook with a clear
  explanatory `_comment` field, on top of the baseline `Stop` report hook.
- **SMAIRT008, SMAIRT009, and SMAIRT010 messages are uniformly excellent** — each names
  the exact rule, the exact file, and a concrete next action:
  - SMAIRT008: *"'prompted_by: X' does not resolve to a real unit under experiments/;
    fix the folder name, or remove the field if this question was not actually
    prompted by another unit's result."*
  - SMAIRT009: *"hypothesis: is empty; write the one-line claim this question tests
    before treating any run as evidence for or against it."*
  - SMAIRT010: *"...write what you measured and how you judged the result before
    closing (amend it with '**Amended YYYY-MM-DD:**' if the plan changed after it was
    written)."* — the one place this message is misleading is the renamed-heading case
    (M-2), not the message's content.
- **Unit numbering respects hand-made folders**: creating a stage while a hand-made
  `01_legacy_stage` folder already sits in `experiments/` correctly continues at `02_`
  rather than colliding — the numbering authority reads the filesystem, not an internal
  counter.
- **`smairt check` resolves the project root correctly from a deep subdirectory** and
  reports every finding path relative to that root, not the cwd.
- **Every `--json` output tested parses as valid JSON**: `smairt check --json`,
  `smairt status --json`, and `smairt data list --json` were each round-tripped through
  `json.load()` and confirmed structurally sound (`findings`/`suggestions`/`summary`;
  `focus`/`spine`/`live_questions`/...; `datasets`).
- **Invalid `--harness` values, empty `smairt connect` invocations, and `--receipt`
  without `--tool`** all fail with a clean one-line, exit-appropriate message — no
  crash anywhere in ordinary Typer-level input validation.
