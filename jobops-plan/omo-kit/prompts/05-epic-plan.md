ulw plan

Optional, for one epic at a time: turn plan/epics/<EPIC>.md and its story files into an OmO plan in .omo/plans/<EPIC>.md.
Keep story order, task order and every Red test exactly as written — the OmO plan is an execution checklist for the existing plan, not a new design.
Then run: /ulw-execute <EPIC> --worktree ../jobops-<EPIC> --make-pr
