# 11. How comparable frameworks handle orientation, structure growth, and provenance state

Research ticket for the SMAIRT architecture investigation. All claims cite primary sources
(official docs, repos, or the projects' own user research). Anything not traceable to a
primary source is explicitly marked **unverified**.

Frameworks surveyed: cookiecutter-data-science (CCDS), DataLad, Kedro, Quarto
(projects/manuscripts), showyourwork, Snakemake + workflow catalog, eLabFTW (ELN), plus
evidence on Jupyter-notebook-as-lab-notebook practice.

---

## Lessons (synthesis first)

**1. The most-documented abandonment cause is heavy day-one scaffolding, from the
frameworks' own retrospectives.** Kedro's published user research records users calling the
generated template "an intimidating number of files and directories generated just by
starting a project" and "a lot of boilerplate for what can be remarkably simpler analysis,"
and notes that needing to touch at least three files (catalog, node, pipeline) to add one
feature was "so overwhelming for some that they step away" from the framework
([Kedro wiki: Research summary of insights](https://github.com/kedro-org/kedro/wiki/Research-summary-of-insights-for-improving-Kedro's-value)).
CCDS v1's fixed `src/` layout drew the same pressure and v2 both renamed `src` to the
project's module name and made most scaffolding an opt-in prompt (`ccds` asks per-project
about environment manager, docs, testing, scaffolding)
([issue #140](https://github.com/drivendataorg/cookiecutter-data-science/issues/140),
[CCDS docs](https://cookiecutter-data-science.drivendata.org/)). Lesson: scaffold the
minimum on day one; every unexplained directory is a tax paid at first contact and again at
every onboarding.

**2. The state models that survived contact with users are derived-from-files, with Git as
the database.** Quarto: a directory *is* a project because `_quarto.yml` exists — no
registration step, no hidden registry
([Quarto projects](https://quarto.org/docs/projects/quarto-projects.html)). DataLad: all
state is the Git/git-annex history itself; even provenance records are JSON embedded in
commit messages ([DataLad handbook, `datalad run`](https://handbook.datalad.org/en/latest/basics/101-108-run.html)).
Snakemake: what-needs-doing is derived from file timestamps/checksums plus a hidden
`.snakemake/` metadata cache — the user never edits state, only files
([Snakemake rules docs](https://snakemake.readthedocs.io/en/stable/snakefiles/rules.html)).
The one surveyed system with fully explicit state — eLabFTW's MySQL database — survives
too, but only by becoming a server product with an admin, TLS, and Docker deployment
([eLabFTW docs](https://doc.elabftw.net/)); that cost model does not fit a per-project
framework.

**3. Re-orientation ("what was I doing, what next") is the least-solved problem in
file-based frameworks — and the one users demonstrably pay for elsewhere.** CCDS offers
nothing beyond README/Makefile conventions. Kedro needed a whole separate tool (Kedro-Viz)
to answer "what does this project look like," including a Workflow view for inspecting
execution and errors ([Kedro-Viz docs](https://docs.kedro.org/projects/kedro-viz/en/stable/)).
DataLad gives `datalad status` (a git-status analogue)
([handbook](https://handbook.datalad.org/en/latest/basics/101-102-populate.html)) and
Snakemake gives dry-run/`--summary`/`--list-code-changes` to see what would run and why
([rules docs](https://snakemake.readthedocs.io/en/stable/snakefiles/rules.html)) — both
answer "what is stale," not "what was I doing." eLabFTW, the only tool scientists adopt
*specifically* as their lab memory, leads with exactly the orientation features the others
lack: editable color-coded status labels, tags, search "as easy as a google search,"
templates, and cross-links between experiments ([eLabFTW docs](https://doc.elabftw.net/)).
Lesson: orientation is a real, purchasable feature; file-based frameworks mostly skipped it
and left users with `git log`.

**4. Provenance that rides inside the repo beats sidecar state — and the winning format is
machine-readable records bound to commits.** DataLad's run record is JSON in the commit
message mapping command → inputs → outputs, and `datalad rerun` replays it
([handbook](https://handbook.datalad.org/en/latest/basics/101-108-run.html)).
showyourwork compiles PDFs whose figure margin links "point to the exact version of the
script (i.e., to the specific commit SHA on GitHub) that was used to generate the figure"
([quickstart](https://show-your.work/en/latest/quickstart/)). Quarto tells you to commit
`_freeze/` "so that others rendering the project don't need to reproduce your computational
environment" ([code execution docs](https://quarto.org/docs/projects/code-execution.html)).
The counterexample is the bare notebook: of ~1.4M Jupyter notebooks on GitHub, only ~24%
ran at all and ~4% reproduced their own stored results — hidden state and out-of-order
execution being top causes
([Pimentel et al. 2019](https://leomurta.github.io/papers/pimentel2019a.pdf)). Provenance
must be captured at run time by tooling, or it does not exist.

**5. Growth is user-driven everywhere that works; enforcement belongs at the publication
boundary, not day one.** CCDS's stated philosophy: "be liberal in changing the folders
around for *your* project, but be conservative in modifying the default"
([CCDS opinions](https://cookiecutter-data-science.drivendata.org/opinions/)). Kedro fixes
only two files' locations (`pipeline_registry.py`, `settings.py`) and lets the rest flex
([Kedro concepts](https://docs.kedro.org/en/stable/get_started/kedro_concepts.html)). The
Snakemake workflow catalog is the cleanest model: minimal rules to be listed at all, and a
stricter "standardized usage" tier (`workflow/Snakefile`, `config/README.md`,
`.snakemake-workflow-catalog.yml`) that is *opt-in and machine-checked only when you want
the badge* ([catalog docs](https://snakemake.github.io/snakemake-workflow-catalog/docs/catalog.html)).
No surveyed framework has a human/agent "approval" step for structure growth; conventions
plus automated lint at the sharing boundary is the observed pattern.

**Implications for SMAIRT (scientists + AI assistants):**

- **State model: hybrid, weighted toward derived.** Derive "what is stale / what ran" from
  files and Git (the Snakemake/DataLad model — it never lies and never needs manual
  upkeep). Keep a *small* explicit file for what cannot be derived: intent, current
  question, next step — the thing eLabFTW's status labels carry. Explicit state that
  duplicates derivable facts rots; every surveyed system that stores facts twice (notebook
  outputs vs. code) measurably diverges (Pimentel). Machine-readable plain-text state
  (YAML/JSON in-repo, DataLad-style commit records) is also exactly what an AI assistant
  can read and update without a service running.
- **Orientation: generate it, don't maintain it.** A status command/report synthesized from
  Git history + the intent file (DataLad `status` + eLabFTW dashboard, merged) — not a
  hand-curated log, which is the notebook-discipline model that fails.
- **Day-one scaffolding: minimal, with a documented growth path.** Kedro's own research is
  the strongest signal in this entire survey: intimidating initial file trees cause
  walk-aways *before first value*. Start near-empty (Quarto's "one config file makes it a
  project"), grow by convention, and lint structure only at the sharing/publication
  boundary (catalog model).

---

## Per-framework detail

### cookiecutter-data-science (DrivenData)

- **Where state lives.** No runtime state at all. Machine-readable artifacts are the
  generated config: `pyproject.toml` (package metadata + tool config), `setup.cfg`,
  `requirements.txt` (or chosen alternative), and a `Makefile` encoding project commands.
  Everything else is directory convention
  ([CCDS docs](https://cookiecutter-data-science.drivendata.org/)).
- **Fixed vs grown.** Fully scaffolded at creation via the `ccds` CLI, which prompts for
  environment manager, dependency format, testing, linting, docs, and code scaffolding —
  i.e., v2 made much of the v1 fixed skeleton opt-in
  ([CCDS docs](https://cookiecutter-data-science.drivendata.org/)). Growth is explicitly
  user-approved: "A consistent default … be liberal in changing the folders around for
  *your* project, but be conservative in modifying the default"; the opinions page shows
  worked examples of flattening and expanding the tree as projects evolve
  ([opinions](https://cookiecutter-data-science.drivendata.org/opinions/)). Core data
  discipline is the DAG: raw data immutable, `raw/ → interim/ → processed/`
  ([opinions](https://cookiecutter-data-science.drivendata.org/opinions/)).
- **Re-orientation.** Nothing. No status command, no dashboard. The docs' answer to project
  memory is process advice: document experiments (data provenance, code version, metrics),
  "starting with simple JSON formats before graduating to tools like MLflow"
  ([opinions](https://cookiecutter-data-science.drivendata.org/opinions/)).
- **Criticisms / abandonment.** Users pushed back on the generic `src/` package
  (issue asking to rename `src` to the project name, closed into the v2 milestone —
  [issue #140](https://github.com/drivendataorg/cookiecutter-data-science/issues/140));
  v2's template now names the package `{{ cookiecutter.module_name }}`
  ([docs](https://cookiecutter-data-science.drivendata.org/)). The proliferation of
  organization-specific forks (GDS, Nesta, etc. — visible in any search) shows the default
  tree gets rewritten per-organization rather than adopted verbatim; the docs themselves
  concede notebooks win for exploration and prescribe "refactor the good parts into source
  code" as the countermeasure ([opinions](https://cookiecutter-data-science.drivendata.org/opinions/)).
  **Unverified:** no primary-source statistics exist on how many generated folders go
  unused in practice.

### DataLad

- **Where state lives.** Entirely in Git + git-annex: large files live in the annex with
  symlinks in the worktree; dataset state *is* repository state
  ([handbook](https://handbook.datalad.org/en/latest/basics/101-102-populate.html)).
  Provenance is machine-readable JSON embedded in commit messages by `datalad run`
  (`cmd`, `dsid`, `inputs`, `outputs`, `exit`, `pwd`, delimited by "Do not change lines
  below" markers), consumed by `datalad rerun`
  ([handbook, run](https://handbook.datalad.org/en/latest/basics/101-108-run.html)).
  `datalad download-url` similarly stores "a hidden, machine-readable record of the origin
  of the content" ([handbook](https://handbook.datalad.org/en/latest/basics/101-102-populate.html)).
- **Fixed vs grown.** No imposed directory layout at all — DataLad manages *any* tree.
  Structure growth is entirely the user's, including nesting datasets.
- **Re-orientation.** `datalad status` (untracked/modified/clean, git-status style) and the
  Git log itself, which — because run records live in commits — doubles as an executable
  lab log ([handbook](https://handbook.datalad.org/en/latest/basics/101-102-populate.html),
  [run](https://handbook.datalad.org/en/latest/basics/101-108-run.html)). No higher-level
  "what was I doing" view.
- **Criticisms / abandonment.** The handbook's own FAQ concedes "a necessary investment is
  to learn how to use this tool," and documents the symlink foot-guns: "what *appears* to
  be the file in the dataset is merely a symlink," copying it "will not yield the intended
  result – instead you will have a broken symlink," unretrieved files confuse tools like
  the BIDS validator, and copied-out annexed files are read-only
  ([FAQ](https://handbook.datalad.org/en/latest/basics/101-180-FAQ.html)). **Unverified:**
  broader abandonment patterns (e.g., labs dropping DataLad for complexity) are not
  documented in primary sources I could reach; the learning-curve admission above is the
  strongest first-party evidence.

### Kedro

- **Where state lives.** Declarative config in `conf/base/` (`catalog.yml` — "the registry
  of all data sources that the project can use," `parameters.yml`) with per-machine
  secrets/overrides in git-ignored `conf/local/`; `pyproject.toml` "identifies the project
  root and contains configuration information"
  ([Kedro concepts](https://docs.kedro.org/en/stable/get_started/kedro_concepts.html)).
  All machine-readable YAML/TOML; no runtime database in core.
- **Fixed vs grown.** `kedro new` scaffolds `conf/`, `src/`, plus optional `data/`,
  `docs/`, `notebooks/`, `tests/` depending on tool selection — so day-one weight is now
  partly opt-in. Hard constraints are minimal: `pipeline_registry.py` and `settings.py`
  must stay in `src/<package>/`; "while the default structure is recommended, you can adapt
  the folder structure to your needs"
  ([concepts](https://docs.kedro.org/en/stable/get_started/kedro_concepts.html)).
- **Re-orientation.** Not in the CLI — it took a separate product, Kedro-Viz: interactive
  pipeline visualization, metadata panels, and a Workflow view to "inspect execution,
  errors, and dataset stats"
  ([Kedro-Viz docs](https://docs.kedro.org/projects/kedro-viz/en/stable/)).
- **Criticisms / abandonment (first-party user research — the best evidence in this
  survey).** Kedro's own research wiki records: an "overwhelming and intimidating number of
  files and directories" from initialization; "a lot of boilerplate for what can be
  remarkably simpler analysis"; needing to "touch at least three files to add new features
  (catalog, node, and pipeline)" being "so overwhelming for some that they step away";
  notebook users hitting a paradigm wall; repeated onboarding confusion over what `conf`,
  `setup.cfg`, `pyproject.toml` are for; and non-adoption when the opinionated layout
  conflicted with existing team structure
  ([Research summary wiki](https://github.com/kedro-org/kedro/wiki/Research-summary-of-insights-for-improving-Kedro's-value)).
  The team openly frames itself as "opinionated by design"
  ([Kedro blog](https://kedro.org/blog/development-principles-for-opinionated-teams)).

### Quarto (projects and manuscripts)

- **Where state lives.** A directory is a project iff it contains `_quarto.yml` (global +
  per-format options, with `_metadata.yml` per subdirectory and document-level YAML
  overriding upward; `.local` config variants stay out of version control)
  ([projects docs](https://quarto.org/docs/projects/quarto-projects.html)). Computation
  cache: "The computational results of documents executed with `freeze` are stored in the
  `_freeze` directory," and the docs instruct: "You should check the contents of `_freeze`
  into version control so that others rendering the project don't need to reproduce your
  computational environment"
  ([code execution](https://quarto.org/docs/projects/code-execution.html)). **Unverified:**
  internals of the `.quarto/` working directory are not described in the docs pages
  fetched.
- **Fixed vs grown.** Nearly structureless: project types (website, book, manuscript) add
  behavior, not mandated trees. Manuscript projects accept "one or more notebooks or `.qmd`
  documents" and grow by adding files
  ([manuscripts docs](https://quarto.org/docs/manuscripts/)). Growth is implicit —
  rendering picks up what exists; no approval step.
- **Re-orientation.** None for process state; re-execution state is handled automatically —
  `freeze: auto` re-runs a document only "when their source file changes"
  ([code execution](https://quarto.org/docs/projects/code-execution.html)). The manuscript
  *site* is itself an orientation artifact for readers: article + embedded notebook cells +
  full rendered notebooks + MECA archive "designed to capture your article and its
  supporting documents" ([manuscripts](https://quarto.org/docs/manuscripts/)).
- **Criticisms / abandonment.** The docs themselves flag the freeze escape-hatch semantics
  (incremental renders always execute; clearing state = delete `_freeze/`)
  ([code execution](https://quarto.org/docs/projects/code-execution.html)).
  **Unverified:** merge-conflict pain from committing `_freeze/` is commonly reported but I
  did not verify a primary-source discussion; treat as anecdote.

### showyourwork

- **Where state lives.** In-repo config: `showyourwork.yml`, `Snakefile`, `environment.yml`
  (conda), `zenodo.yml`; execution state via the underlying Snakemake machinery; remote
  cache of intermediate results on Zenodo when enabled ("automatically caches the results
  of intermediate steps") ([layout](https://show-your.work/en/latest/layout/),
  [quickstart](https://show-your.work/en/latest/quickstart/)).
- **Fixed vs grown.** Rigid by design: `showyourwork setup` creates `src/tex`,
  `src/scripts`, `src/static`, `src/data`, `.github/workflows/`; renames require config
  edits, and "most users shouldn't have to tweak" the build files. Growth = adding scripts
  and custom Snakemake rules within that frame
  ([layout](https://show-your.work/en/latest/layout/)).
- **Re-orientation.** For readers, exceptional: every figure's margin link "points to the
  exact version of the script (i.e., to the specific commit SHA on GitHub) that was used to
  generate the figure," GitHub Actions rebuilds the article "from scratch on the cloud" on
  every push, and repo badges expose build state
  ([quickstart](https://show-your.work/en/latest/quickstart/)). For the *author* returning
  after a gap: only the Snakemake dry-run machinery underneath; no author-facing status.
- **Criticisms / abandonment.** The README states plainly "showyourwork! is a work in
  progress"; repo signals as of this fetch: 663 stars, 60 open issues
  ([repo](https://github.com/showyourwork/showyourwork)). Its changelog documents a
  major overhaul of versioning and dependency management (moving deps like tectonic into
  conda envs) — evidence the reproducibility surface was fragile enough to need re-architecting
  ([changelog](https://show-your.work/en/latest/changelog/)). **Unverified:** specific
  "old articles no longer build" issue threads — widely believed, not confirmed against a
  primary source in this pass. Lesson regardless: end-to-end reproducibility tools carry a
  large maintenance surface (LaTeX + conda + Snakemake + CI + Zenodo), and their guarantees
  are only as durable as the weakest pinned layer.

### Snakemake + workflow catalog

- **Where state lives.** Derived + hidden cache: staleness computed from input/output
  timestamps, with checksums recorded for small files ("for small input files … Snakemake
  instead records and compares file checksums"); job metadata "stored in the `.snakemake`
  directory inside your working directory"; code-change tracking exposed via
  `--list-code-changes`/`--summary`
  ([rules docs](https://snakemake.readthedocs.io/en/stable/snakefiles/rules.html),
  [reporting docs](https://snakemake.readthedocs.io/en/stable/snakefiles/reporting.html)).
  The user never edits this state.
- **Fixed vs grown.** Snakemake itself imposes nothing. The *catalog* defines a two-tier
  convention: listing requires only a public repo, a README mentioning
  "snakemake"+"workflow," and a `Snakefile`/`workflow/Snakefile`; the opt-in "standardized
  usage" tier additionally requires `workflow/Snakefile`, "configuration instructions under
  `config/README.md`," and a root `.snakemake-workflow-catalog.yml` configuring generated
  usage instructions — all machine-checked by the catalog, i.e., structure is *approved by
  a linter at the publication boundary*, never during development
  ([catalog docs](https://snakemake.github.io/snakemake-workflow-catalog/docs/catalog.html)).
- **Re-orientation.** `--dry-run` (what would run), `--summary`/`--list-code-changes`
  (what is stale and why), and post-hoc `snakemake --report`: a self-contained HTML report
  with "runtime statistics, provenance information and workflow topology by default"
  ([rules](https://snakemake.readthedocs.io/en/stable/snakefiles/rules.html),
  [reporting](https://snakemake.readthedocs.io/en/stable/snakefiles/reporting.html)).
  Again: answers "what is stale," not "what was I thinking."
- **Criticisms / abandonment.** The catalog's very existence (blacklist, minimal tier vs
  strict tier) is evidence that most real-world Snakemake repos do *not* follow the full
  standard — the strict tier had to be made opt-in. **Unverified:** proportion of catalog
  workflows meeting the standardized tier (the catalog UI shows the split but I did not
  capture numbers).

### eLabFTW (electronic lab notebook)

- **Where state lives.** Fully explicit, external to any project directory: a MySQL
  database behind a Docker/Podman-deployed server ([docs](https://doc.elabftw.net/)).
  Machine-readable via API/exports; nothing lives with the analysis code.
- **Fixed vs grown.** No directory model at all; structure = experiments, database items,
  templates, tags — grown freely by users, with team-level templates as the convention
  mechanism ([docs](https://doc.elabftw.net/)).
- **Re-orientation.** This is the product: search "as easy as a google search," "color
  coded statuses (that you can edit at will)," a tagging system "to keep track of family
  of experiments," templates, and links between experiments and items
  ([docs](https://doc.elabftw.net/)). Note the status vocabulary is *user-editable* — the
  tool does not impose a lifecycle.
- **Provenance.** "Full audit log and revision history for entries," RFC3161 trusted
  timestamping, locking/immutable archives, cryptographic signatures, and near-total action
  logging ([docs](https://doc.elabftw.net/)) — compliance-grade, but decoupled from code:
  the ELN records *that* you did something, not a re-runnable recipe.
- **Criticisms / abandonment.** The deployment requirements themselves (Linux server,
  Docker, MySQL, TLS admin) are the documented adoption cost
  ([docs](https://doc.elabftw.net/)). **Unverified:** lab-level abandonment patterns.

### Jupyter notebooks as lab notebooks (evidence baseline)

- Pimentel et al., *A Large-scale Study about Quality and Reproducibility of Jupyter
  Notebooks* (MSR 2019): of ~1.4M notebooks on GitHub, only ~24.1% executed without error
  and only ~4% reproduced the same results; leading causes were missing dependencies,
  hidden state / out-of-order execution, and inaccessible data
  ([paper PDF](https://leomurta.github.io/papers/pimentel2019a.pdf)). This is the null
  hypothesis for SMAIRT: self-reported, manually-maintained computational state — the
  notebook's stored outputs — diverges from reality in ~96% of cases. Any state SMAIRT
  keeps must be either derived automatically or verified automatically.

---

## Answers to the consuming decisions

**Explicit, derived, or hybrid state?** Hybrid, derived-first. Derived state (Snakemake
staleness, Quarto freeze, DataLad-from-Git) is the only kind shown to stay truthful without
user discipline; explicit state earned its keep only where it captures *intent and status*
that no tool can derive (eLabFTW's editable status labels, tags). The proven serialization
for the explicit sliver is machine-readable plain text bound to the repo (DataLad's JSON
run records in commits; the catalog's `.snakemake-workflow-catalog.yml`) — which is also
the form an AI assistant can read, diff, and update with no daemon.

**How heavy should day-one scaffolding be?** Light. The single strongest primary-source
finding in this survey is Kedro's own research: initial file-tree weight causes walk-aways,
and per-change multi-file ceremony causes step-aways
([Kedro wiki](https://github.com/kedro-org/kedro/wiki/Research-summary-of-insights-for-improving-Kedro's-value)).
Both CCDS v2 (opt-in scaffolding prompts) and Kedro (tool-selection flags) retreated from
their original day-one weight. The successful pattern is Quarto's "one file makes it a
project" plus the catalog's "strict structure only when you publish, checked by a machine."
For SMAIRT: minimal creation footprint, structure grown by documented convention with the
assistant as the linter, and full rigor enforced only at the sharing/publication boundary.
