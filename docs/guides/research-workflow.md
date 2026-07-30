# Research workflow

SMAIRT turns a research project into linked, reviewable records. Commands can create and validate
those records, but consequential scientific transitions remain researcher decisions.

## Restore context before acting

Begin each session by inspecting the current project rather than relying on chat history:

```bash
smairt status --json
smairt next --json
smairt next --prompt
smairt context --task planning --token-budget 8000
```

The JSON output is intended for scripts and assistants. The prompt output is a bounded handoff with
suggested files and an explicit human-decision boundary.

## Build a source-grounded background

Add references before treating a background statement as supported. A local PDF, DOI metadata, or
Zotero record becomes an attributed project reference; discovery results remain provisional until
selected and imported.

```bash
smairt reference add path/to/paper.pdf
smairt reference add-doi 10.1000/example --confirm-remote
smairt reference list
smairt background create
smairt background validate
```

The background should distinguish what indexed sources support, what the researcher infers, and
what evidence is missing. Reference metadata fetched from a provider is not automatically
human-verified.

## Compare directions before selecting one

```bash
smairt hypothesis proposals new
smairt hypothesis proposals validate hypotheses/proposals/PROPOSAL_SET_001.md
```

A proposal set contains three meaningfully distinct options with reasoning, falsifiable
predictions, alternatives, required data, feasibility, and confounders. An assistant may draft or
challenge them. A confirmed contributor must select or revise the scientific direction:

```bash
smairt hypothesis activate \
  --proposal-set hypotheses/proposals/PROPOSAL_SET_001.md \
  --option A --title "Selected direction" \
  --statement "A specific falsifiable statement" \
  --selected-by "Researcher Name" \
  --rationale "Why this option is scientifically preferred"
```

An experiment may instead declare a clear exploratory purpose. SMAIRT does not require a
hypothesis merely to make the project appear complete.

## Design experiments and iterations

```bash
smairt experiment new --title "Baseline test" --hypothesis HYPOTHESIS_001
smairt code index
smairt code validate
```

Each experiment has iterations. Create a new iteration for a meaningful change in method,
configuration, input definition, control, or interpretation criterion. Do not rewrite an earlier
iteration to hide the path taken.

Schema-8 experiments include `protocol.yaml`. Declare inputs, expected outputs, controls, success
and failure criteria, uncertainty, interpretation limits, and stopping rules before execution.

## Run through the provenance boundary

```bash
smairt run --experiment EXPERIMENT_001 --iteration ITERATION_001
smairt verify --json
```

Run reservation happens under the project mutation lock. The child process executes without that
lock, then SMAIRT records terminal status, command, configuration, entrypoint, packages, Git state,
logs, results, protocol digest, and integrity hashes. Failed and interrupted runs remain visible
and cannot become accepted evidence.

Never edit a run bundle. Correct the method in a new iteration or append an explicit correction.

## Interpret before accepting evidence

Before ACCEPT on a protocol-required experiment, complete:

1. `result-summary.yaml` in the run bundle (artifact checksums matching outputs)
2. `analysis/EXPERIMENT_*/ANALYSIS_ITERATION_*.md` with headings
   `## Observed Results`, `## Interpretation`, and `## Limitations and Confounders`
3. Integrity verification (`smairt verify --run RUN_<id>`)
4. Known Git provenance when Git is enabled for the project

Use the run ID printed by `smairt run`:

```bash
smairt verify --run RUN_<timestamp> --json
smairt decision record --experiment EXPERIMENT_001 --iteration ITERATION_001 \
  --run RUN_<timestamp> --decision ACCEPT \
  --rationale "How the observed result met the predefined criterion" \
  --decided-by "Researcher Name"
```

The decision is a human gate. Verification shows that the bundle is internally consistent; it
does not prove that the method, data, or interpretation is scientifically correct.

Accepted runs can be reviewed into evidence cards:

```bash
smairt paper evidence review --run RUN_<timestamp> \
  --purpose "Predeclared purpose" \
  --observed-result "What was directly observed" \
  --limitations "Known limitations and confounders" \
  --decision ACCEPT
```

## Build claims and manuscript sections

```bash
smairt paper claim propose \
  --statement "A bounded claim supported by the result" \
  --evidence evidence-run_<timestamp>
smairt paper claim approve claim-<id> --yes
smairt paper outline
smairt paper begin --title "A Traceable Study"
```

Paper prose can use current accepted evidence, approved claims, and reviewed references. Every
section is reviewed before a build. Markdown and DOCX outputs are versioned; a failed template or
validation step does not replace a prior build.

## Correct without rewriting history

If accepted evidence is invalid, append a retraction:

```bash
smairt retract --run RUN_<timestamp> --reason "Why the result is no longer valid"
```

For a replacement, create and verify a new iteration and run, then link the correction:

```bash
smairt supersede --run <old-run> --replacement-run <new-run>
```

Dependent selections, evidence, and claims become stale while the earlier record remains
inspectable.

## Collaborate through Git

Use a branch or worktree for each contributor or independent line of work. The project lock
protects one checkout; it does not coordinate multiple worktrees or resolve scientific meaning.

```bash
smairt contributor add --name "Second Researcher"
smairt contributor use second-researcher
smairt lock status --json
```

If a multi-file operation stops, inspect its journal before completing or rolling it back:

```bash
smairt recovery status --json
smairt recovery complete <transaction-id> --yes
# or, after review
smairt recovery rollback <transaction-id> --yes
```

Before sharing, run project validation and the appropriate safety checks. Repository visibility is
contacted only when explicitly refreshed:

```bash
smairt doctor --json
smairt validate --staged
smairt safety status --refresh-visibility --json
smairt safety release-check --json
```
