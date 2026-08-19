# Day-one scaffold weight

Type: grilling
Status: resolved
Blocked by: 01, 07

## Question

What does `smairt new` generate by default? Today: fourteen wizard screens, ~50 files, ~4,400 lines of guidance, all three phase trees — an explicit invariant defended by `adversarial_review1.md` (clone durability, vanishing directories). The handout wants a minimal foundation that grows when research earns it.

Decide the default footprint, what "earned growth" looks like mechanically, and how the durability lessons from the adversarial review are preserved without shipping everything on day one.

## Answer

**Day-one scaffold — nine items, identical for every project and user:**

```text
my_project/
├── smairt.yaml       # identity
├── STATUS.md         # focus / next / open questions
├── AGENTS.md         # 1-page contract + project-learnings section
├── CLAUDE.md         # 2-line bridge to AGENTS.md (or selected harness bridge)
├── .gitignore
├── background/       # question.md, literature/, prior_work/ — context, never code
├── data/             # datasets, each with a provenance-header README
├── scripts/          # shared reusable code, called by experiments with parameters
├── experiments/      # the work: numbered stages + dated questions
└── results/INDEX.md  # generated signpost: every figure & log → its unit
```

**`scripts/` restored (researcher's catch, with the PNNL rationale):** reusable code — HPC helpers, analysis routines, plotting — lives once in `scripts/` and experiments *call* it with different parameters; the unit records the invocation (script pointer + `params:` in its header, log in `logs/`). This is an anti-drift mechanism: it stops LLMs rewriting near-identical analysis code per experiment. The receipt convention covers it — calling your own shared script is recorded like calling an outside tool. Rule: code called by more than one experiment lives in `scripts/`; one-off probe code stays in its unit. Guidance instructs the assistant to prefer extending a shared script (a *notable*-stakes proposal) over writing a new variant. Day-one scaffold is therefore **ten items**.

**One `experiments/` folder, not two** — spine-ness is header metadata (`kind: stage` vs `kind: question`), so projects without pipelines carry no empty folders and numbered stages sort above dated questions (spine on top, probe timeline below). Model S is adopted: units are self-contained; interpretation ("What it means") lives in the unit README beside its evidence — the old `analysis/` file merged in. Hypotheses at two levels: project question in `background/question.md`; each probe's hypothesis in its unit README, written before the run; multi-probe lines live in STATUS.md until they earn a grouping folder. **Standard subfolders in every unit: `logs/`, `out/`, `figures/`** — outputs live in-unit (researcher chose A). Central views are derived (`smairt status`, generated `results/INDEX.md`), never a second copy.

**Units contain or reference — three cases:** (1) own code lives in the unit; (2) outside tools get a *receipt* unit — tool/version/command/log fields, born as a tool-generated fill-in form, checked for empty fields and unresolvable pointers; (3) pre-existing projects via `smairt adopt`, which lays the contract around existing files and moves nothing — **deferred to stretch-goal status**: the researcher starts fresh as the test case; PNNL projects adopt only after the shape survives real use.

**Growth mechanics:** creation-time opt-ins (2–3 plain questions at `smairt new`: expect HPC? expect a paper?); mechanical growth detection by `smairt check` (SLURM script appears → suggest `hpc/`; paper-words in STATUS → suggest Paper overlay; question clusters → suggest grouping), surfaced through the same hook channel as drift warnings; structural additions are proposal-gated with a one-paragraph why, and unproposed top-level folders are flagged as drift. **Strictness:** out-of-structure writes are a session-end warning by default; hard pre-tool blocking is an optional `smairt` setting, off by default.

**Human edits are first-class:** the tool writes skeletons once and never regenerates researcher words; `smairt check` validates structure (fields exist, pointers resolve), never wording.
