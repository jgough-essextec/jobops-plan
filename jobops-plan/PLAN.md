# JobOps — Master TDD Build Plan

**A combined job-search application: Paperclip orchestrates a company of Hermes agents that drive JobSpy and career-ops on Doc's behalf.**

| | |
|---|---|
| Owner | Doc |
| Runtime host | GB10 Spark (Tailscale), managed from phone |
| Status | Plan v1.0, 2026-11-14 |
| Companion files | `00-INDEX.md` (traceability + dependency graph), `epics/`, `stories/` |

---

## 1. Goal

Build one application, **JobOps**, that continuously:

1. **Finds** relevant roles (JobSpy across job boards, plus career-ops portal scanning).
2. **Scores** them against Doc's profile (career-ops A–F evaluation).
3. **Makes** tailored artifacts for the good ones (career-ops CV + cover letter + PDF).
4. **Reviews** those artifacts with an independent critic *before* Doc sees them.
5. **Watches the inbox** for responses, ties each one to its application, and turns it into a decision brief with a draft reply.
6. **Hands every consequential action to Doc.** JobOps never submits an application and never sends an email.

All of this is coordinated by a **Manager agent** inside **Paperclip**. Every agent is a **Hermes** agent running through Paperclip's `hermes_local` adapter.

### Success metrics (pilot exit criteria, see E12)
| Metric | Target |
|---|---|
| New, de-duplicated, pre-screened roles surfaced per week | ≥ 25 |
| Duplicate rate in what Doc sees | < 2% |
| A/B-tier jobs with a reviewed artifact set within 24h | ≥ 90% |
| Critic catch rate on seeded defects (calibration set) | ≥ 90%, false-positive rate ≤ 15% |
| Fabricated claims in artifacts shown to Doc | 0 (hard gate) |
| Inbox responses matched to the right application | ≥ 95% |
| Auto-submitted applications / auto-sent emails | 0 (hard gate) |
| Monthly LLM spend | within the budget Doc sets in Paperclip |

---

## 2. Components and how they fit

| Component | What it is | Role in JobOps |
|---|---|---|
| **Paperclip** | Open-source Node.js server + React UI that runs a "company" of AI agents: org chart, issues (tickets), heartbeats, budgets, approvals, audit trail, REST API | Orchestration layer and the place Doc acts as **the board** |
| **Hermes Agent** (Nous Research) | Agent runtime with tools, persistent memory, skills, MCP support. Run by Paperclip's `hermes_local` adapter as a single-query `hermes chat -q` per heartbeat, with `--resume` session persistence | Runtime for all five agents |
| **career-ops** (santifer) | Job-search system for AI coding CLIs: markdown evaluation *modes* (A–F scoring), tailored CV generation, Playwright PDF, portal scanner, tracker, `npm run doctor` | Evaluation, tailoring, PDF, portal scanning, tracker |
| **JobSpy** (`python-jobspy`) | Python library; `scrape_jobs()` aggregates LinkedIn, Indeed, Glassdoor, Google, ZipRecruiter etc. into a pandas DataFrame; proxy support | Board-level discovery |
| **LiteLLM gateway** | Model router | One endpoint for local Nemotron (vLLM) and cloud judges (Claude Opus, Gemini) |
| **Notion** | Tracker Doc already uses | Doc's read/act surface for the pipeline |
| **Telegram** | Phone notifications | Approve / Revise / Skip from the phone |
| **Kanban boards** | Two drag-and-drop boards over the same ledger | **Pipeline board** in Notion (columns = job stages, S10.5). **Agent-work board**: Paperclip's own Board view if it supports drag and drop (S10.7), otherwise a small React + `@dnd-kit` web app (S10.8). A spike (S10.6) decides. |

### 2.1 Architecture

```
                        ┌──────────────────────── Doc (the board) ────────────────────────┐
                        │  Paperclip UI  ·  Telegram bot  ·  Notion "JobOps" database       │
                        └───────────────▲───────────────────────────▲─────────────────────┘
                                        │ approvals / comments      │ status / briefs
┌───────────────────────────────────────┴───────────────────────────┴───────────────────────┐
│ PAPERCLIP  — company "JobOps"  (issues · heartbeats · budgets · approvals · audit)         │
│                                                                                            │
│                         ┌────────────────────────┐                                         │
│                         │ MANAGER  (CEO role)    │  sweeps ledger, routes, escalates       │
│                         └───┬──────┬──────┬──────┘                                         │
│              ┌──────────────┘      │      │      └───────────────┐                         │
│        ┌─────▼─────┐   ┌───────────▼┐  ┌──▼────────┐   ┌────────▼───────┐                  │
│        │  SCOUT    │   │  TAILOR    │  │  CRITIC   │   │  CONCIERGE     │                  │
│        │  search + │   │  artifacts │  │  review   │   │  inbox watch + │                  │
│        │  evaluate │   │  + revise  │  │  (judge)  │   │  decision brief│                  │
│        └─────┬─────┘   └─────┬──────┘  └────┬──────┘   └───────┬────────┘                  │
│   all agents: adapterType hermes_local → `hermes chat -q` (resume session)                 │
└──────────────┼───────────────┼──────────────┼──────────────────┼───────────────────────────┘
               │ MCP           │ MCP          │ MCP              │ MCP
     ┌─────────▼───┐  ┌────────▼──────┐  ┌────▼─────┐   ┌────────▼──────┐   ┌──────────────┐
     │ jobspy-mcp  │  │ careerops-mcp │  │ review-  │   │  inbox-mcp    │   │  ledger-mcp  │
     │ (JobSpy     │  │ (career-ops   │  │ checks   │   │ (Gmail RO +   │   │  (source of  │
     │  wrapper)   │  │  bridge)      │  │          │   │  drafts)      │   │   truth)     │
     └─────────────┘  └───────────────┘  └──────────┘   └───────────────┘   └──────┬───────┘
                                                                                    │ sync
                                                                        Notion · Telegram
                         LiteLLM gateway: Nemotron (local vLLM) · Claude Opus · Gemini
```

### 2.2 Key design decisions (ADRs to write in E00)

| # | Decision | Why |
|---|---|---|
| ADR-1 | **Agents never shell out to JobSpy or career-ops free-form.** Every capability is a typed MCP tool (`jobspy-mcp`, `careerops-mcp`, `ledger-mcp`, `inbox-mcp`). | Typed tools give us contracts to test, least privilege, and an audit trail. Free-form shell is untestable. |
| ADR-2 | **The JobOps Ledger (SQLite) is the source of truth** for job state. Paperclip issues, Notion rows and the career-ops tracker are projections. | One state machine, one place to test transitions; sync can be rebuilt. |
| ADR-3 | **career-ops is split.** Deterministic parts (PDF, tracker, doctor, scan) run through a bridge. LLM-reasoning parts (evaluation, tailoring) run inside the Hermes agent, using career-ops `modes/*.md` as Hermes skills. The bridge validates output against a schema on submit. | Respects career-ops' design (built to be driven by an AI CLI) while keeping outputs contract-checked. |
| ADR-4 | **The Critic uses a different model family from the Tailor** (e.g., Tailor = Nemotron, Critic = Claude Opus or Gemini). | Independent review, so the work isn't grading itself. |
| ADR-5 | **Hard human gate.** No tool exists that submits an application or sends an email. Inbox scope is read + create-draft only. | The safety guarantee is enforced by what's absent, not by prompts. Tested as a release gate (S11.3). |
| ADR-6 | **Company-as-code.** Paperclip company, agents, budgets, heartbeats, prompt templates and skills are declared in `paperclip/company.yaml` and applied idempotently. | Reproducible, reviewable, diffable; drift is detectable. |
| ADR-7 | **Testing seam: fake Hermes.** Paperclip's `hermesCommand` points at a scriptable fake CLI in tests. | Lets us run the whole orchestration deterministically in CI with no LLM calls. |
| ADR-8 | **Model routing only through LiteLLM**, with per-agent virtual keys. | Swap models without touching agents; spend is attributable per agent. |
| ADR-9 | **Agent-work board: configure Paperclip or build our own**, decided by the S10.6 spike. Both boards use one `board_rules.yaml` generated from the state machine, so a drag is only allowed where Doc may make that move. | Paperclip's docs describe a Board view but not dragging between columns. One rule file keeps the two boards (and Telegram) consistent. |

---

## 3. The agent company

| Agent | Paperclip role / reports to | Default model | Heartbeat | Tools (MCP) | Writes ledger states |
|---|---|---|---|---|---|
| **Manager** | CEO → board (Doc) | Nemotron (local) | every 2h + on comment/assignment | `ledger-mcp` (read, transition), Paperclip API (issues, assign), `notify` | routes everything; ARCHIVED, ESCALATED |
| **Scout** | Reports to Manager | Nemotron | 2×/day + on assignment | `jobspy-mcp`, `careerops-mcp.scan`, `careerops-mcp.evaluate.*`, `ledger-mcp` | DISCOVERED, SCREENED_OUT, EVALUATED |
| **Tailor** | Reports to Manager | Nemotron (Opus for A-tier, optional) | on assignment | `careerops-mcp.profile/tailor/pdf`, `artifact-store`, `ledger-mcp` | TAILORING, DRAFTED, REVISED |
| **Critic** | Reports to Manager | Claude Opus or Gemini (≠ Tailor) | on assignment | `review-checks`, `careerops-mcp.read`, `ledger-mcp`, Paperclip approvals | IN_REVIEW → READY_FOR_DOC / REVISE / BLOCKED |
| **Concierge** | Reports to Manager | Nemotron (judge escalation for offers) | every 30 min | `inbox-mcp` (read, label, create_draft), `ledger-mcp`, `notify` | RESPONDED, INTERVIEWING, REJECTED, OFFER |

**Doc is the board.** Doc approves artifacts, changes to search profiles, budget changes and new agents, and is the only one who applies or sends.

---

## 4. Pipeline state machine (owned by the Ledger, E01)

```
DISCOVERED ──► SCREENED_OUT (hard filter)            ──► ARCHIVED
     │
     ▼
EVALUATED ──(tier C)──► HOLD ──(Doc promotes)──► SHORTLISTED
     │  (tier D/F) ──► ARCHIVED (with reason)
     ▼ (tier A/B)
SHORTLISTED ──► TAILORING ──► DRAFTED ──► IN_REVIEW
                                  ▲            │
                                  │  REVISE (≤2 loops)
                                  └────────────┤
                                               ├──► BLOCKED ──► ESCALATED (to Doc)
                                               ▼
                                         READY_FOR_DOC ──(Doc: revise)──► TAILORING
                                               │ (Doc: approve)
                                               ▼
                                           APPROVED ──(Doc applies, confirms)──► APPLIED
                                                                                   │
                                     Concierge ──► RESPONDED ──► INTERVIEWING ──► OFFER
                                                         └────► REJECTED ──► ARCHIVED
```
Rules: transitions are guarded; illegal transitions raise; each transition writes an append-only event naming the actor (agent id or `doc`); `APPLIED` can only be set by actor `doc`.

---

## 5. TDD strategy

### 5.1 The loop, for every task
1. **Red:** write the failing test(s) named in the task. Commit them (`test:` prefix) before any implementation.
2. **Green:** write the least code that passes.
3. **Refactor:** clean up with all tests green; no behavior change.
4. **Prove:** CI green, coverage threshold met, the task's DoD ticked in the PR description.

### 5.2 Test pyramid and tooling

| Layer | What | Tooling | Runs |
|---|---|---|---|
| Unit | Pure logic: normalizers, state machine, rubrics, routing rules, parsers | `pytest` + `hypothesis` (Python), `vitest` (TS) | every commit |
| Contract | Our wrappers vs. the real shapes of JobSpy output, career-ops files/scripts, Paperclip API, Gmail API, Notion API | Recorded fixtures (`vcrpy`, saved DataFrames as parquet, captured JSON); schema tests with JSON Schema | every commit |
| Component | One service + its MCP surface, with fakes behind it | MCP client test harness, `testcontainers` | every commit |
| Agent behavior (evals) | An agent's decisions given scripted inputs: right tools, right order, right ledger transitions, no forbidden actions | Fake Hermes (scripted) for orchestration; **live-model eval suite** with golden sets for reasoning quality | fake: every commit; live: nightly + before release |
| Integration | Paperclip + fake Hermes + all MCP services + fakes for Gmail/Notion/Telegram | `docker compose -f compose.test.yml` | every PR |
| E2E / shadow | Real models, real boards, test Telegram chat, Notion sandbox DB | On the Spark | nightly during build; pilot |

### 5.3 Test doubles (built early, reused everywhere)
| Double | Replaces | Built in |
|---|---|---|
| `fake-hermes` CLI | Hermes in Paperclip (`hermesCommand`) | S04.2 |
| LiteLLM mock route | Models, for deterministic agent-level tests | S00.5 |
| JobSpy fixture replay | Live scraping | S00.4, S02.2 |
| career-ops fixture profile (`fixtures/careerops/`) | Doc's real CV in tests | S00.2 |
| Fake mailbox (GreenMail IMAP + Gmail API stub) | Doc's inbox | S09.1 |
| Notion stub server, Telegram stub | External UIs | S10.1, S10.2 |

### 5.4 Test-case ID convention
`TC-<epic>.<story>-<nn>`, e.g. `TC-02.3-04`. Tags: `[unit]`, `[contract]`, `[component]`, `[agent]`, `[eval]`, `[integration]`, `[e2e]`, `[guardrail]`. Anything tagged `[guardrail]` is in the release-blocking suite (S11.3).

---

## 6. Definition of Done (three levels)

### Task DoD (applies to every task unless the task says otherwise)
- [ ] Failing test(s) committed first and visible in history
- [ ] Implementation passes them; no skipped or xfail tests added
- [ ] Coverage of new or changed code ≥ 90% (lines) for logic modules
- [ ] Lint, type-check (`ruff`, `mypy --strict`, `tsc --noEmit`) clean
- [ ] Public functions have docstrings; non-obvious decisions commented

### Story DoD
- [ ] All tasks meet Task DoD
- [ ] All story test cases implemented and passing in CI
- [ ] Acceptance criteria demonstrated (CI output, recording, or screenshot linked in PR)
- [ ] No new secrets in repo; any new config documented in `docs/config.md`
- [ ] Ledger states / MCP tool contracts changed? → schema version bumped and contract tests updated
- [ ] PR reviewed and merged to `main`; story file status set to **Done**

### Epic DoD
- [ ] All stories Done
- [ ] Epic exit criteria met (listed in each epic file)
- [ ] Integration suite green on `main`
- [ ] Runbook / docs section for the epic written
- [ ] Demo to Doc (5 minutes, from the phone where relevant)

---

## 7. Epics and sequence

| Epic | Name | Depends on | Phase |
|---|---|---|---|
| E00 | Foundations & discovery spikes | — | 0 |
| E01 | Domain core & pipeline ledger | E00 | 1 |
| E02 | JobSpy discovery service | E00, E01 | 1 |
| E03 | career-ops bridge | E00, E01, E02 | 1 |
| E04 | Paperclip company & Hermes runtime | E00, E01 | 1 |
| E05 | Manager agent | E01, E03, E04, E10 | 2 |
| E06 | Scout agent (search) | E02, E03, E04, E05, E10 | 2 |
| E07 | Tailor agent (artifacts) | E01, E03, E04, E05 | 2 |
| E08 | Critic agent (review) | E03, E04, E07, E10 | 2 |
| E09 | Concierge agent (inbox) | E00, E01, E04, E05 | 3 |
| E10 | Human interface (Notion, Telegram, approvals) | E00, E01, E04, E08 | 2–3 |
| E11 | Observability, safety & governance | E00, E01, E03, E04, E07, E09, E10 (starts early, closes last) | 1–4 |
| E12 | Integration, shadow run & release | E05–E11 | 4 |

Epic dependencies are derived from story-level dependencies (a script checks they agree). **E08 and E10 interleave** rather than run in sequence: S10.2 (Telegram bot) → S08.4 (hand-off to Doc) → S10.3 (approval workflow). There is no cycle at story level.

**Phases:** 0 Spikes (de-risk the three external libraries before writing wrappers) → 1 Platform (ledger, wrappers, Paperclip) → 2 Core pipeline (Manager, Scout, Tailor, Critic, approvals) → 3 Inbox loop → 4 Hardening & pilot.

**Critical path (by story points, computed in `00-INDEX.md`):** S00.1 → S00.2 career-ops spike → S01.1–S01.4 ledger → S03.3 evaluation → S03.4 provenance → S03.5 PDF → S07.1 Tailor → S08.3 Critic → S08.4 hand-off → S10.3 approvals → S12.1 E2E → S12.2 shadow → S12.4 pilot. Paperclip work (E04) and JobSpy work (E02) run in parallel beside it.

Full story-level dependency graph and the traceability matrix are in **`00-INDEX.md`**.

---

## 8. Repository layout

```
jobops/
├── paperclip/
│   ├── company.yaml            # company-as-code (agents, budgets, heartbeats)
│   ├── prompts/<agent>.hbs     # hermes promptTemplate per role
│   └── skills/<skill>/SKILL.md # agent skills (tool usage, rubrics)
├── services/
│   ├── ledger/                 # domain model, state machine, SQLite, ledger-mcp
│   ├── jobspy_svc/             # JobSpy wrapper + jobspy-mcp
│   ├── careerops_bridge/       # career-ops bridge + careerops-mcp
│   ├── review_checks/          # deterministic artifact checks
│   ├── inbox/                  # Gmail/IMAP connector + inbox-mcp
│   ├── notion_sync/            # ledger → Notion projection + pipeline board
│   ├── telegram_bot/           # notifications + inline actions
│   ├── board_api/              # (Path B) backend for the Kanban web app
│   └── board_ui/               # (Path B) React + dnd-kit Kanban web app
├── vendor/career-ops/          # git submodule, pinned
├── fakes/                      # fake-hermes, notion stub, telegram stub, mailbox seed
├── evals/                      # golden sets + live-model eval harness
├── tests/integration/          # compose-based tests
├── compose.yml / compose.test.yml
└── docs/ (ADRs, runbook, config)
```

---

## 9. Risks and mitigations

| Risk | Likelihood | Impact | Mitigation | Story |
|---|---|---|---|---|
| Job boards rate-limit or block JobSpy (429s, LinkedIn limits) | High | Med | Per-site isolation, backoff, proxies, modest `results_wanted`, fixtures for CI | S02.4 |
| career-ops is built to be driven interactively by an AI CLI; no stable headless API | High | High | Spike first (S00.2); bridge pins to a commit; contract tests catch upstream changes on upgrade | S00.2, S03.1 |
| Paperclip / adapter API changes (young, fast-moving projects) | Med | High | Pin versions; contract fixtures; company-as-code drift check | S00.3, S04.3 |
| Hallucinated CV claims | Med | Very high | Provenance check (every claim maps to master CV), Critic fidelity rubric, `[guardrail]` test | S03.4, S08.1, S11.3 |
| Prompt injection via job descriptions or emails | Med | High | Treat JD/email as data; tool allow-lists per agent; no send/submit tools exist; injection eval set | S09.6, S11.3 |
| Spend overrun | Med | Med | Paperclip per-agent budgets (soft 80%, hard 100%), LiteLLM per-key limits, local model as default | S04.5, S11.1 |
| Terms-of-service exposure from scraping | Med | Med | Personal-use volumes, respect robots/rate limits, prefer official APIs/portals where available | S02.4 |
| Two boards and Telegram disagree for a moment | Med | Low | Ledger is the source of truth; boards re-sync from it via live updates; shared board_rules | S10.5, S10.8 |
| Notification fatigue | Med | Med | Daily digest by default; real-time only for READY_FOR_DOC, interview requests and offers | S05.4, S10.2 |

---

## 10. Assumptions (change these and the affected stories move)
1. Inbox is **Gmail** (Gmail API, `gmail.readonly` + `gmail.compose` for drafts only). IMAP fallback included for other providers.
2. Notion and Telegram stay Doc's human surfaces (consistent with the existing job-agent design).
3. Hosting is the GB10 Spark; Paperclip runs locally with its default embedded database; JobOps Ledger is SQLite on the same box with nightly backup.
4. Autonomy stays at *drafts only*: Doc approves every application, tiered by fit score.
5. Upstream versions are pinned at the commits recorded in the E00 spikes.

---

## 11. How it gets built
The build runs in **OmO (oh-my-openagent) ultrawork mode**. See `omo-kit/BUILD-WITH-OMO.md`. `omo-kit/setup-repo.sh` creates the repo with this plan under `plan/`, an `AGENTS.md` contract, `.omo/` config and rules, and `plan/tools/build_state.py`. That tool picks the next ready story from the dependency graph and parks stories that need Doc (`plan/checkpoints.yaml`).
