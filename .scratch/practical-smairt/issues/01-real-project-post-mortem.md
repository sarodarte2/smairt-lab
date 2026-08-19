# Real-project post-mortem

Type: grilling
Status: resolved

## Question

What specifically broke when the ongoing real research project was forced out of SMAIRT? Which conventions were abandoned first, which files became convoluted, what mixed with what, and at what point in the project's growth? If the project (or a redacted copy) can be shared, examine it directly; otherwise reconstruct the failure modes by interview.

Output: a ranked list of observed failure modes with concrete examples. This is the evidence anchor most other tickets cite — the difference between designing against observation and designing against recollection.

## Answer

Conducted as an interview (project files not examined). The researcher's real project — differential-expression / RNA-seq work — left SMAIRT **within the first few days**. Ranked failure modes:

1. **Supervision collapse (root failure).** The scaffold's complexity outran the researcher's comprehension, and the system's only protection — approval — became rubber-stamping: "I felt often compelled to approve... I would just sort of approve." Anatomy of the rubber stamp, in the researcher's own ranking: **standing** most of all (the AI felt like it "just knew better"; imposter syndrome; "I could not keep up"), plus missing **explanation in the researcher's terms** and undifferentiated **stakes** (every decision the same apparent size). The AI compounded this by overengineering and solving problems outside the researcher's expertise without explaining. Consequence for the design: the binding constraint is the researcher's **comprehension budget** — a mechanism that exceeds it doesn't merely fail, it converts human authority into apparent consent. "Complexity must be supervisable" is stronger than "complexity must be earned."
2. **Work-shape mismatch.** The real work is a **spine pipeline** (align → count → QC → DE), rerun and tweaked until frozen, **plus exploratory probe branches** off it. SMAIRT's only work unit — the iteration (one script, one log, one interpretation) — fits neither the spine nor the branching, so the layout had nowhere to put half the work. Broke exactly when parallel ideas, pipelines, HPC runs, and multiple analysis kinds arrived.
3. **Ledger overload.** The record files were "too many"; maintaining them was "mind-numbing." Staleness followed, then distrust.
4. **Convention decay.** Numbering/naming (script_NN, HYPOTHESIS_NN) stopped being followed once the ledgers died.
5. **Scatter.** Dead ends mixed with keeper results; investigation lines shared folders; outputs and logs mixed into data/script folders; no subfolder discipline; helper/guidance files mixed with science. "It is too much."
6. **Nothing demonstrated value.** Asked what must survive (hypothesis-first discipline, raw-log separation, phase progression), the answer was **"almost none of it got a chance to help."** Core principles must therefore be re-derived from SMAIRT's philosophy, not inferred from the shipped implementation.

Note recorded over the researcher's own framing: "mainly my own level of skill" is rejected as a diagnosis. A co-developer and domain scientist is the most favorable user this tool will ever have; if supervision failed for them, the skill floor is a design defect. This also revises the audience decision: the design must be supervisable by audience B (any scientist with an AI assistant), not just audience A.
