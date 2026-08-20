# SMAIRT Domain Context

SMAIRT creates and manages readable, file-based scientific research workspaces.

## Glossary

| Term | Meaning |
|---|---|
| Unit | The atomic folder of research work under `experiments/`: a stage, a question, or a thin reference variant of either. The sole thing `smairt unit new` creates; a researcher or assistant never `mkdir`s one by hand. |
| Stage | A unit that is one step of the project's spine. Folder `NN_slug/`, numbered automatically and only ever upward. Status is one of active, frozen, or dead-end. |
| Question | A unit that is one exploratory probe. Folder `YYYY-MM-DD_slug/`, dated rather than numbered. Status is one of open, supported, refuted, inconclusive, or dead-end; closing it (any status but open) requires a non-empty verdict and a non-empty `## Analysis plan`. |
| Reference unit | A thin, README-only stage or question — no `logs/`, `out/`, or `figures/` — whose frontmatter carries `paths:` pointing at code or output that already exists outside `experiments/`. What `smairt adopt` produces for pre-existing work; never framed as a testable claim, so it is exempt from the hypothesis and Analysis plan rules. |
| Spine | The planned sequence of a project's work, expressed as its numbered stages read top-down. |
| Hypothesis | A question unit's one-line testable claim, held in `hypothesis:`. Required to hold real text for any status, open or closed — the point is that it exists before the run, not only once the question closes. |
| Analysis plan | The stated rule for what a question unit will measure and how its outcome will be judged, written before the run wherever possible. Revisions keep the original and append a marked amendment rather than replacing it. |
| Prompted by | The relationship between a question unit and the earlier unit whose result raised it. Recorded on the *newer* unit as `prompted_by:`. A question earns its own unit — rather than staying a note inside the unit that raised it — once a new testable claim can be stated in one line. |
| Verdict | A question unit's recorded answer to its own stated hypothesis, held in `verdict:`. Required non-empty once the question closes; never covers a finding that isn't about that hypothesis — an incidental finding earns its own unit instead. |
| Receipt | A unit whose frontmatter records an outside tool's run — `tool:`, `tool_version:`, `command:`, and optionally `repo:` — instead of copying the tool itself into the project. Once `tool:` is set, its `tool_version:`, `command:`, and `log:` must all actually be filled in and the log must exist. |
| Evidence pointer | A frontmatter field — `script:`, `log:`, `outputs:`, or `paths:` — naming a path that must resolve to something real. A closed unit is held to the strict reading: the file itself must exist, and `script:`/`log:` may not be blank. An open unit's not-yet-run `log:` counts as resolved while its containing folder exists, so a freshly created question passes before anything has run. `paths:` resolves from the project root; every other pointer resolves from the unit's own folder. |
| Frontmatter | The `---`-delimited YAML block at the top of a unit README or `STATUS.md`, holding that file's structured fields. Everything below it is free-text body, read only for its section headings, never inspected or judged. |
| Finding | One violation of a rule: an id, a severity (error or warning), the offending path, and a message. Any finding at all makes `smairt check` exit non-zero. |
| Suggestion | One advisory, growth-channel note from a check. Never affects `smairt check`'s exit code. |
| Rule | One check `smairt check` runs against the project's units, frontmatter, and state, carrying one stable id that is never renumbered once shipped. `SMAIRT001`–`SMAIRT013` produce findings and can fail the check; `SMAIRT101`–`SMAIRT105` produce advisory suggestions and never affect the exit code. The rule, not each way of violating it, is the unit of identity. |
| Contract | The workflow conventions a project commits to: written once, in `AGENTS.md`, generated identically whether the project came from `smairt new` or `smairt adopt`; verified mechanically ever after by `smairt check`'s rules. |
| Harness | One assistant CLI tool `smairt connect` knows how to wire up: Claude Code, Codex, OpenCode, Gemini CLI, Cursor, or pi. |
| Harness wiring | The generated, per-harness files — hook config, a bridge file where one is needed, and copies of SMAIRT's skills — that let a harness read and run the project's contract. Every file names itself as generated and is safe to delete; none of them ever runs a `smairt` command that writes. |
| Bridge file | A small generated file that exists only for a harness that does not read `AGENTS.md` natively (e.g. Claude Code's `CLAUDE.md`); it imports `AGENTS.md` so that harness still follows the one contract. A harness that reads `AGENTS.md` on its own gets no bridge file. |
| Skill | One of the assistant-facing `smairt-*` procedures the package ships and `smairt connect` installs into a harness's skills directory. Model-invocable by default; the one exception is researcher-invoked only, enforced on the harnesses that support it. |
| Dataset | One subfolder under `data/` with its own README recording where its bytes physically live, created by `smairt data new` and never a central registry file. |
| Dataset location | One place a dataset's bytes can be found: `local` (inside the project's own `data/`), `hpc` (a path on a named remote host), or `url` (a download source). Recorded in a dataset's frontmatter `locations:` list; `smairt data locate` appends one, idempotently. |
| Adoption | The contract-around process, run by `smairt adopt`, that lays SMAIRT's contract files around a pre-existing project directory without moving, renaming, or editing anything already there. Reference units are how the pre-existing work itself later joins the record. |
| Project root | The directory holding a project's identity file, `smairt.yaml`. Every `smairt` command walks upward from its working directory to find the nearest one, the same way Git finds a repository root by looking for `.git`. |
| Golden fixture | A checked-in example generated project that `smairt check` must always pass clean, and that a freshly generated project is compared against byte-for-byte to catch scaffold drift. |
