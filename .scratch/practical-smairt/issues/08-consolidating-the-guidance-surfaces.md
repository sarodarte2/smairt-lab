# Consolidating the guidance surfaces

Type: grilling
Status: resolved
Blocked by: 01, 10

## Question

Nine AI-guidance surfaces ship today: `AI_CONTEXT.md`, `CONTEXT_INDEX.md`, `00_priming_prompts.md`, `KNOWN_PATTERNS.md`, `CODE_CONVENTIONS.md`, `12_STEPS.md`, `SMAIRT_PHILOSOPHY.md`, `session_log.md`, plus per-harness skills. What is the minimal canonical set, which single source of truth do the others derive from, and what gets deleted outright?

Researcher's framing (added during grilling): this ticket covers the whole agent-facing implementation layer — skills, prompts, context/token optimization strategies, rules, hooks — and the goal is structure that helps agents and people *both at the same time*. Prune what is unnecessary; whatever mattered in the pruned files moves into files that actually get used and stuck to; the researcher should feel no friction unless necessary.

## Answer

**The three-tier system** (resolves the researcher's "AGENTS.md guides, it does not enforce" concern — correct, so the design minimizes what rests on prose):

1. **Generated correctly** (strongest): unit READMEs are skeletons written by the tooling (skills / `smairt` commands) with correct frontmatter and section structure already in place. Conventions are applied at creation time, not remembered. This is also the answer to "how do folder READMEs guide writing conventions" — they *are* the instantiated template.
2. **Checked mechanically**: `smairt check` validates the checkable — frontmatter schema, legal statuses, STATUS.md drift, no loose files outside units — wired into harness hooks and CI.
3. **Advised** (weakest, smallest): only the ungeneratable/uncheckable (scientific practice, cheap-data-first, researcher-owns-conclusions) lives as prose.

**Project guidance inventory:** one short `AGENTS.md` (~1 page: the two units, header format, the loop in ten lines, safety rules) + thin bridges (2-line CLAUDE.md import; Gemini setting). An appendable **project learnings** section at its foot replaces KNOWN_PATTERNS/CODE_CONVENTIONS for *project-specific* knowledge, with hard size discipline (assistant prunes as it appends); *generic* conventions move into the SMAIRT-owned skills. **Deleted from projects:** AI_CONTEXT.md, CONTEXT_INDEX.md, 00_priming_prompts.md (skills replace priming), 12_STEPS.md, SMAIRT_PHILOSOPHY.md, session_log.md, iteration_review/figure prompts.

**Procedures live in multiple small SMAIRT-owned skills** (researcher's choice over one large skill), shipped and versioned with the tool, never copied into projects. Assume all supported harnesses handle skills (researcher's directive). Candidate set (final list is spec work): orient/resume, new question, new stage, record decision + update status, fork (contained→propagating mechanics), adversarial review. Each skill both instructs and *does the template instantiation* — tier 1 above.

**Hook wiring:** when the researcher selects a harness (at `smairt new` or later via `smairt connect <harness>`), SMAIRT installs that harness's hook config — visible, commented, running only read-only `smairt check`. Researcher-initiated, tool-executed.
