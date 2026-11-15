# AGENTS.md — JobOps

You are building **JobOps**: Paperclip orchestrates five Hermes agents (Manager, Scout, Tailor, Critic, Concierge) that drive JobSpy and career-ops for Doc's job search. The full plan lives in `plan/`. **The plan is the spec. Do not redesign it; build it.**

## Where things are
| What | Where |
|---|---|
| Architecture, ADRs, TDD strategy, global Definition of Done | `plan/PLAN.md` |
| Dependency graph, build waves, guardrail test list | `plan/00-INDEX.md` |
| Epics | `plan/epics/E*.md` |
| Stories (tasks, Red tests, test cases, DoD) | `plan/stories/E*/S*.md` |
| Build progress (source of truth for what's next) | `plan/status.yaml` via `python plan/tools/build_state.py` |
| Things only Doc can do | `plan/checkpoints.yaml` |

## The build loop (follow exactly)
1. `python plan/tools/build_state.py next` → pick the **first** ready story (or several if running in parallel; never two stories that touch the same service at once).
2. `python plan/tools/build_state.py start <ID>`; create branch `story/<ID>-<slug>` (or a worktree per story when parallel).
3. Read the story file end to end, plus every upstream story it names.
4. For each task, in order:
   - **Red:** write the tests listed under "Red". Run them. They must fail for the right reason. Commit: `test(<ID>): <task title>`.
   - **Green:** minimum code to pass. Commit: `feat(<ID>): <task title>`.
   - **Refactor:** tidy with tests green. Commit: `refactor(<ID>): …` if anything changed.
5. Implement every test case in the story's **Test cases** table (IDs `TC-xx.y-nn`; tag guardrail tests with `@pytest.mark.guardrail` / `describe.guardrail`).
6. Run `make test lint typecheck` and the guardrail suite once it exists. All green.
7. Tick the story's Definition of Done in the PR body. Open a PR to `main`; merge only when CI is green.
8. `python plan/tools/build_state.py done <ID>`. If it prints `waiting_on_doc`, write a short note for Doc in `plan/DOC-INBOX.md` (what to review, where) and **move on to the next ready story — do not wait.**
9. Repeat until `build_state.py next` is empty. Then run `build_state.py report`, append it to `plan/DOC-INBOX.md`, and stop.

## Hard rules
- **Tests first, always.** A commit that adds implementation without a failing test before it is a defect; redo it.
- **Never edit a test to make it pass** unless the story file says the test is wrong; if so, note it in the PR.
- **Never skip or xfail** a test to get green. If you cannot get green after 3 honest attempts, `build_state.py block <ID> "<why>"`, write the blocker in `plan/DOC-INBOX.md`, and take the next ready story.
- **Never clear a checkpoint.** `build_state.py clear` is Doc's command only.
- **Never use real personal data.** No real CV, email, inbox, Notion or Telegram content in the repo, fixtures or logs. Synthetic fixtures only.
- **Never add a capability JobOps must not have:** sending email, submitting applications, `gmail.send` scope, posting to job boards. The guardrail tests exist to catch this; do not weaken them.
- **Live network calls only in spikes** (S00.2–S00.4, S10.6) and only after the checkpoint allows it. CI uses fixtures and fakes.
- **Pin versions** of Paperclip, Hermes, career-ops, JobSpy as the spikes record them. Do not upgrade upstream without an upgrade story.
- **Spikes produce knowledge**: ADRs + fixtures + contract tests. Keep spike code under `spike/`; do not ship it.
- If a story is ambiguous, choose the reading most consistent with `PLAN.md`, record it under "Decisions" in the PR, and continue.
- If a plan file is wrong (e.g., an upstream API differs from what a story assumes), fix the story file in the same PR and explain why — then implement against reality.

## Done means
Story DoD in the story file + `PLAN.md §6`. Not "it runs on my machine".
