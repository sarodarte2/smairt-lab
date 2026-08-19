# Minimum anti-bias mechanism

Type: grilling
Status: resolved
Blocked by: 03

## Question

What is the smallest mechanism that keeps an assistant from gradually making one hypothesis canonical? Candidates from the handout: explicit alternatives, recorded assumptions, unresolved-question lists, hypothesis provenance, adversarial checkpoints, route comparison. Today this concern is addressed only by prose exhortation in `AI_CONTEXT.md`. Decide which mechanism (if any) earns its cost, and whether it needs state from the research-state contract or stays procedural.

Post-mortem finding this ticket must design against: the observed failure was **supervision collapse**, ranked by the researcher as (1) standing — the AI felt like it "just knew better"; (2) explanation not in the researcher's terms; (3) undifferentiated stakes causing approval fatigue. An alternatives table alone addresses none of these. The mechanism must restore the researcher's ability to *evaluate*, not just present more options to approve.

## Answer

Exactly three mechanisms, each mapped to an observed failure — nothing heavier:

1. **Stakes labels** (vs. approval fatigue): the assistant tags every proposal *routine / notable / structural*. Only structural requires an explicit yes; routine flows. Enforced as an AGENTS.md rule plus skill behavior.
2. **The explanation rule** (vs. missing explanation and standing): any notable-or-above proposal must state, in plain language, (a) what it does, (b) what it risks *scientifically*, and (c) one alternative and why not. The researcher evaluates instead of deferring. The recorded alternatives double as the decision/contribution trail — this is the surviving fate of `intellectual_contribution.md`, which dies as a separate file.
3. **Adversarial-review skill** (vs. one interpretation becoming canonical): researcher-invoked at checkpoints; argues *against* the current interpretation from the evidence recorded in the units — dead ends, unexplained surprises, open questions.

No new files, no scoring systems, no per-decision logs: anything heavier becomes new complexity the researcher must supervise, which was the original disease.
