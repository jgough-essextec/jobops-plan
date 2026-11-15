ultrawork

Build JobOps end to end, following AGENTS.md exactly.

Objective: every story in plan/ is done, waiting_on_doc, or wont_do, with CI green on main.

Loop:
- `python plan/tools/build_state.py next`. Take the first ready story. Run the AGENTS.md build loop on it (Red → Green → Refactor per task, all test cases, DoD, PR, merge on green CI, `build_state.py done`).
- When a story ends waiting_on_doc, or a story can't start because it needs Doc, write the ask in plan/DOC-INBOX.md and continue with the next ready story. Never wait, never clear checkpoints.
- Use smaller models (category `quick`) for fixtures, renderers, docs and lint fixes; `deep` for implementation; `architect` for spikes, ADRs, state machine and company-as-code; `ultrabrain` only when stuck.
- After each story, re-read AGENTS.md hard rules before starting the next.

Stop when `build_state.py next` is empty. Then append `build_state.py report` to plan/DOC-INBOX.md and summarize what Doc needs to do.
