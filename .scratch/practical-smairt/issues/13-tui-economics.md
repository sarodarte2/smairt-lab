# TUI economics

Type: grilling
Status: resolved
Blocked by: 02

## Question

About 63% of the Python (~2,800 of ~4,440 lines: `cli.py`, `terminal.py`, `menu.py`, `appearance.py`) serves the fourteen-screen wizard and framed dashboard. If it disappeared tomorrow and `smairt` were plain subcommands, what would a researcher actually lose? Decide whether the interactive layer survives at current scale, shrinks, or is frozen — weighed against the maintenance it costs the one-week implementation and every week after.

## Answer

Decided by the researcher during the one-week-scope grilling: **shrink, with full remake acceptable**. The wizard becomes a short prompt-based `smairt new`; the framed dashboard, framed screens, semantic palette, and action-token machinery are not carried forward. Rationale: the daily research surface is the agentic harness/IDE, not a TUI; the researcher's criteria are works / useful / approachable / consistent / safe for science, and the interactive layer served none of the post-mortem's failure modes. Detail lives in [The one-week scope](02-the-one-week-scope.md).
