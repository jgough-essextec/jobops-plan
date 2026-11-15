# TDD (always on)
- Red → Green → Refactor per task, in the order the story lists tasks.
- The Red tests named in a task are written and run (failing) before any implementation; commit them first.
- Never weaken, skip, or xfail a test to get green. Three honest attempts, then `build_state.py block`.
- Changed-line coverage ≥ 90% for logic modules; ruff + mypy --strict + tsc --noEmit clean.
