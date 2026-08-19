# Phase trichotomy: principle or accident

Type: grilling
Status: resolved

## Question

Is synthetic → downloaded → real a core SMAIRT principle or a computational-biology-shaped historical choice? The repo bakes it in as an invariant (all three directories always exist), yet its own skill hedges: "Do not claim that every project must traverse every phase."

Keep it as an invariant, demote it to an optional capability, or generalize it into the track/route concept? The answer reshapes the directory layout, the wizard, and the contract.

## Answer

**Accident as structure; principle as practice.** Decided with the researcher during the work-unit grilling:

- The tripled directory trees (`experiments/01_synthetic|02_downloaded|03_real_data`, mirrored under `data/`) are removed. The researcher's real DE/RNA-seq work never fit them, and the shipped skill already instructed assistants not to enforce traversal.
- What survives is the underlying principle — *test assumptions cheaply before trusting expensive data* — in two forms: (1) **data provenance**: each dataset records what it is (synthetic / public / real) in its own README metadata; (2) **practice guidance**: the canonical AI guidance recommends the cheap-first ordering as a way of working, not a directory shape.
- `starting_phase` / `current_phase` leave the contract along with the structure; provenance of data replaces provenance of project-phase.
