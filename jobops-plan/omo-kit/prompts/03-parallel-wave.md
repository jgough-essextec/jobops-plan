mass ulw

Build the current wave of JobOps stories in parallel.

1. `python plan/tools/build_state.py next` → the ready set.
2. Group ready stories so no two in a group touch the same service directory (see the story files' Context). Run at most 4 at once.
3. Each story runs in its own git worktree on branch `story/<ID>-<slug>` and follows the AGENTS.md build loop exactly (tests first).
4. Merge to main one at a time, rebasing the next on the updated main and re-running CI before each merge.
5. Mark each finished story with `build_state.py done`. Write any Doc asks to plan/DOC-INBOX.md.
6. When the ready set is empty, run `build_state.py next` again; if new stories are ready, repeat; otherwise print the report and stop.
