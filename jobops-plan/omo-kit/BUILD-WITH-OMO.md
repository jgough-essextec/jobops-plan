# Building JobOps with OmO (ultrawork)

This kit lets **OmO (oh-my-openagent)** build JobOps soup to nuts in ultrawork mode, story by story, tests first, with you only stepping in at a short list of checkpoints.

## How it works

```
 omo + ultrawork prompt
        │
        ▼
 build_state.py next ──► story S0x.y ──► Red tests ─► Green ─► Refactor (per task)
        ▲                                   │
        │                                   ▼
        │                      all test cases + DoD ─► PR ─► CI green ─► merge
        │                                   │
        └──────── build_state.py done ◄─────┘
                         │
                         └─ needs Doc? ─► plan/DOC-INBOX.md, move on to the next ready story
```

- `AGENTS.md` (repo root) is the contract OmO follows: the loop, the hard rules, what "done" means.
- `.omo/omo.jsonc` sets models per category so small models do build-and-check work and the big model does spikes, ADRs and hard debugging.
- `.omo/rules/` repeats the TDD and safety rules in short form.
- `plan/tools/build_state.py` is the single source of "what's next": it reads story dependencies from the plan and keeps progress in `plan/status.yaml`. It refuses to start a story whose dependencies aren't done or that's waiting on you.
- `plan/checkpoints.yaml` lists the 14 places only you can act. OmO never clears these.

## 1. Make a sandbox first (do this before any yolo)

Ultrawork plus auto-approval means the agent runs shell commands, installs packages and pushes code without asking. Give it a box where that's safe:

- **Separate environment on the Spark:** a dedicated Linux user (e.g. `jobops-build`) or a dev container with the repo mounted and Docker available (the integration tests need `docker compose`). Not your normal account, no access to `~/.ssh` or your other projects.
- **GitHub:** a fine-grained token scoped to the one `jobops` repo, *without* admin rights, so it can't change branch protection. Protect `main`: require CI (unit, contract, integration, and the guardrail job once S11.3 lands).
- **Model keys:** a dedicated key (or LiteLLM virtual key) with a hard spend limit.
- **No real credentials until a checkpoint asks for them.** No Gmail, Notion or Telegram tokens, and no real CV, in the sandbox until those stories need them. Before then, everything runs on fakes and synthetic fixtures by design.
- **Run inside `tmux`** so the session survives when your phone or laptop disconnects: `tmux new -s jobops`.

## 2. Install and configure OmO

```bash
curl -fsSL https://get.omo.dev/install.sh | bash   # installs the `omo` binary to ~/.local/bin
omo setup        # imports providers/skills/MCP from an existing OpenCode config if you have one
omo doctor
omo doctor --models   # lists the model IDs you can use — put the right ones into .omo/omo.jsonc
```

Edition note: the standalone `omo` command (Senpi edition) is the default install. If you already run OpenCode, the OpenCode edition (`bunx oh-my-openagent install`) has the fullest set of agents and hooks. The prompts in this kit use the shared keywords (`ulw`, `ultrawork`, `mass ulw`, `ulw plan`), so they work with either. The bootstrap prompt records which commands your build actually has.

**Models:** edit `.omo/omo.jsonc`. The IDs in it are placeholders; replace them with what `omo doctor --models` shows. To use your LiteLLM gateway (e.g. Nemotron for the `quick` category), add it as an OpenAI-compatible provider. Setup imports those into `~/.omo/agent/models.json`.

**Yolo / auto-approve:** the OmO docs I could read don't document a single "yolo" switch for the standalone `omo` command. Check `omo --help` and `/help` for an auto-approve or permissions setting in your version. On the Codex edition, `npx lazycodex-ai install --no-tui --codex-autonomous` writes `approval_policy = "never"` and `sandbox_mode = "danger-full-access"`. Whichever you use, use it **only inside the sandbox above**.

## 3. Create the repo and start

```bash
unzip jobops-plan.zip
./jobops-plan/omo-kit/setup-repo.sh ~/src/jobops   # copies plan/, AGENTS.md, .omo/, tools, prompts
cd ~/src/jobops && tmux new -s jobops
omo
```

Then paste, in order:

| Step | Prompt file | What happens |
|---|---|---|
| 1 | `plan/prompts/01-bootstrap.md` | Checks which OmO commands exist, inits git, builds **S00.1** (repo + CI) only, then stops so you can look at the skeleton. |
| 2 | `plan/prompts/02-full-build.md` | **Ultrawork, soup to nuts:** loops through every ready story until nothing is ready, then writes a report to `plan/DOC-INBOX.md`. |
| 2-alt | `plan/prompts/03-parallel-wave.md` | **mass ulw:** builds each wave of independent stories in parallel worktrees (max 4), merging one at a time. Faster, more tokens. Use it once E00 and E01 are done and the patterns are set. |
| 3 | `plan/prompts/04-resume.md` | After you clear checkpoints: picks up your decisions and continues. |
| opt | `plan/prompts/05-epic-plan.md` | Turns one epic into an OmO plan (`.omo/plans/`) and runs `/ulw-execute` with a worktree and PR. Useful if you'd rather go epic by epic. |

If your OmO build has `/goal`, set it once to keep the objective sticky across idle periods: `/goal Every story in plan/ is done, waiting_on_doc or wont_do with CI green on main`. To stop the loop at any time, use `/stop-continuation`. To continue after a disconnect, run `omo -c`.

## 4. Your part: the checkpoints

The build never waits on you. It parks the story and moves on. When you have a minute, open `plan/DOC-INBOX.md` or run:

```bash
python plan/tools/build_state.py report
```

Do the ask, then clear it (only you run this):

```bash
python plan/tools/build_state.py clear S09.1
```

Then paste `plan/prompts/04-resume.md` (or just tell OmO "continue").

| Story | When | What you do |
|---|---|---|
| S00.2 | after | Review the career-ops spike findings and accept ADR-3 (bridge vs. Hermes-skill split). |
| S00.3 | after | Review the Paperclip + hermes_local spike and accept ADR-6 and ADR-7. |
| S00.4 | before | OK live JobSpy scraping from the sandbox (small volumes) and say which sites to enable. |
| S00.5 | before | Give the build sandbox a Tailscale auth key (tagged, ephemeral) and LiteLLM per-agent virtual keys for the mock + one real route. |
| S04.3 | after | Review paperclip/company.yaml (agents, reporting lines, budgets, heartbeats). |
| S05.2 | after | Review routing policy.yaml (tiers, watchlist, red flags, daily cap). |
| S06.4 | before | Label the 40-JD Scout golden set with your expected tier (about 1 hour). |
| S08.1 | after | Review the Critic rubric.yaml. |
| S09.1 | before | Create the Gmail OAuth client (gmail.readonly + gmail.compose + gmail.labels only) and store the refresh token in sops. |
| S10.1 | before | Create the Notion integration, share the JobOps database with it, and provide the token and your Notion user id. |
| S10.2 | before | Create the Telegram bot with BotFather and provide the token and your chat id. |
| S10.6 | after | Accept ADR-9 (Paperclip board path A or custom dnd-kit board path B). Then mark the other story wont-do. |
| S12.2 | before | Put your real master CV and profile.yml in the private profile/ mount (never in the repo), then approve the 7-day shadow run with real models (test Telegram chat, sandbox Notion DB). |
| S12.4 | before | Approve go-live for the pilot week (real inbox label, real Notion, real Telegram). |

**before** = the story can't start until you clear it. **after** = OmO builds it, then it waits for your review before it counts as done. Downstream stories still wait on it.

The longest wait is usually **S10.6 → ADR-9**: after you pick Paperclip's board (path A) or the custom dnd-kit board (path B), tell OmO and it will mark the other story `wont-do`.

## 5. Watching from your phone

- `tmux attach -t jobops` over Tailscale SSH to watch the live session.
- GitHub: one PR per story (`story/<ID>-…`), each showing its Red commit before its Green commit.
- `plan/DOC-INBOX.md` and `build_state.py report` show what's done, what's blocked and what needs you.

## 6. When something goes wrong

| Symptom | What to do |
|---|---|
| A story is `blocked` | Read the reason in the report. Fix the cause (key, version, flaky upstream), then tell OmO "retry <ID>". `start` works from `blocked`. |
| OmO is looping on one failure | `/stop-continuation`, read the PR, give a hint, then resume with `04-resume.md`. |
| A story assumption was wrong (an upstream API differs) | Expected, especially for Paperclip, Hermes and career-ops. AGENTS.md tells OmO to fix the story file in the same PR and explain why. Review those PRs closely. |
| It weakened or skipped a test | Revert the PR. That breaks AGENTS.md's hard rules, and the guardrail suite (S11.3) catches it once it exists. |
| Spend is climbing | Move more work to `quick`, or point `quick`/`deep` at Nemotron through LiteLLM in `.omo/omo.jsonc`. |

## 7. Size of the job

69 stories, 188 tasks, 201 story-level test cases, 253 points across 16 build waves. Treat the first two epics (E00 spikes and E01 ledger) as the calibration run: watch them closely, adjust `AGENTS.md` and the model mix, then let it run.
