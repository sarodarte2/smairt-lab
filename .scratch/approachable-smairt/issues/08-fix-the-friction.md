# Fix what the walk found, with regression tests

Type: task
Status: open
Blocked by: 07

## Question

Work the friction inventory from
[the adversarial walk](07-adversarial-friction-walk.md) into fixes, each with a
regression test that encodes the real failure — not an imagined one.

This ticket cannot be scoped until 07 reports; its size is whatever the walk
found. When it is picked up, first **triage the inventory**:

- **Fix now** — crashes, wrong results, and any message the floor audience could
  not recover from. These are the ticket.
- **Fix later** — real but survivable roughness. Graduate to its own ticket or
  to the map's Not yet specified; do not silently carry it.
- **Working as designed** — record why, in the resolution. An entry dismissed
  without a reason will be rediscovered by the next walk.

Standing requirements:

- Every fix lands with a test in the matching `tests/test_*.py` file, named for
  the failure it prevents.
- Error messages are held to the floor audience's standard: say what went wrong,
  in what file or argument, and what to do next. `cli.py`'s `_fail` helper and
  the `_HOOK_OUTSIDE_PROJECT_MESSAGE` constant are the shape to follow — the
  latter is already an example of an error that teaches rather than reports.
- No raw traceback should reach a user for any input the walk exercised.
- `uv run pytest`, `uv run ruff check .`, `uv run mypy src tests` green.

If the walk surfaces something that is a *design* gap rather than a defect —
a convention that does not exist rather than one that misbehaves — do not fix it
here. Raise it as a new decision ticket on the map.
