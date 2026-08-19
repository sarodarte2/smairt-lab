# Survey: comparable frameworks

Type: research
Status: resolved

## Question

How do comparable research/project frameworks solve orientation, progressive structure, and provenance — and what has demonstrably failed or succeeded? Candidates: cookiecutter-data-science, DataLad, Kedro, Quarto, showyourwork, Snakemake project conventions, and electronic lab notebook tools. Focus on: where project state lives, how "resume after a gap" works, whether structure is fixed or grown, and what users abandoned.

Findings: `.scratch/practical-smairt/research/11-comparable-frameworks.md`

## Answer

Full findings, cited to primary sources (unverifiable items explicitly marked), in `.scratch/practical-smairt/research/11-comparable-frameworks.md`. Conclusions:

1. **Where state lives:** the surviving frameworks derive state from files + Git. Quarto: a project *is* the presence of `_quarto.yml`. DataLad: provenance as replayable JSON run records in commit messages. Snakemake: staleness derived from timestamps/checksums plus a hidden metadata cache. Kedro: declarative YAML split into tracked base + ignored local. The only fully explicit store surveyed (eLabFTW's MySQL) works, but at server-product cost.
2. **Fixed vs grown:** everything successful is user-grown by convention; no surveyed framework has an approval step for growth. Snakemake's workflow catalog is the standout model — strict structure is an opt-in tier, machine-checked only at the publication boundary.
3. **Re-orientation is the least-solved problem** in file-based frameworks. cookiecutter-data-science: nothing. DataLad/Snakemake answer "what is stale," not "what was I doing." Kedro needed a separate product (Kedro-Viz). eLabFTW — the one tool scientists adopt as lab memory — leads with editable status labels, tags, search, and links.
4. **Documented failures:** Kedro's own user-research wiki records "intimidating number of files and directories," "a lot of boilerplate," and three-file ceremony making users "step away." Both CCDS v2 and Kedro retreated from day-one scaffolding weight. Pimentel et al. 2019 (1.4M notebooks: ~24% run, ~4% reproduce) shows manually maintained state rots.

**Implication for SMAIRT:** research state should be hybrid, derived-first — truth derived from files/Git, one small explicit machine-readable intent/status file, orientation generated on demand; day-one scaffolding minimal, structure grown by convention, rigor enforced only at the sharing boundary.
