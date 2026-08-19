# The one-week scope

Type: grilling
Status: resolved
Blocked by: 01

## Question

Given the observed failure modes and one implementation week, which problems must the design record solve, and which are explicitly deferred? The spec's table of contents is decided here. Deferral is a recorded decision, not an omission.

## Answer

**In scope — the five commitments, in order:**
1. The work-unit model — a layout fitting spine pipeline + probe branches, separating dead ends from keepers.
2. A minimal day-one scaffold — a handful of files, not fifty.
3. The research-state contract — one small status file; everything else derived from files/Git.
4. An orientation capability answering "where am I / what next" from that state.
5. Guidance collapsed to one canonical `AGENTS.md` plus `smairt check`.

**Spec format requirement:** the spec must be sliced into subagent-executable pieces — each of the five carries its own mini-handout (context, constraints, acceptance criteria) so implementation subagents can work them independently. This is the researcher's chosen implementation strategy.

**TUI decision (also resolves the TUI-economics ticket):** shrink — the fourteen-screen wizard is replaced by a short prompt-based `smairt new`; the framed dashboard is not carried forward. A full remaking of the code is acceptable. Success criteria, in the researcher's words: works, useful, approachable, consistent, safe to use for science. The daily research surface is the agentic harness/IDE, not the TUI.

**Deferred (recorded, not omitted):** distribution and identity (repo naming mismatch, version confusion, PyPI). Rationale: this week's audience is the researcher alone, stress-testing in the repo; sharing with PNNL is a later gate, and what merges to the main branch is chosen after that. Fixing public-facing identity before the stress-test would polish a door nobody walks through yet.
