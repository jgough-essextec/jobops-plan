"""Render JobOps epics/stories YAML into markdown files with validated dependencies."""
import re, sys, glob, yaml
from pathlib import Path
from collections import defaultdict, deque

SRC = Path(__file__).parent
OUT = Path(sys.argv[1])

epics = yaml.safe_load((SRC / "epics.yaml").read_text())
stories = []
for f in sorted(glob.glob(str(SRC / "stories_*.yaml"))):
    stories += yaml.safe_load(Path(f).read_text())

E = {e["id"]: e for e in epics}
S = {s["id"]: s for s in stories}
assert len(S) == len(stories), "duplicate story ids"

def epic_of(sid): return "E" + sid[1:3]
def slug(t): return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:60]
def epic_file(eid): return f"{eid}-{E[eid]['slug']}.md"
def story_dir(eid): return f"{eid}-{E[eid]['slug']}"
def story_file(sid): return f"{sid}-{slug(S[sid]['title'])}.md"

# ---- validation ----
errors = []
for s in stories:
    if epic_of(s["id"]) not in E: errors.append(f"{s['id']}: unknown epic")
    for d in s["deps"]:
        if d not in S: errors.append(f"{s['id']}: missing dep {d}")
    for k in ("story", "context", "ac", "tasks", "tests"):
        if not s.get(k): errors.append(f"{s['id']}: empty {k}")
    for t in s["tasks"]:
        if not t.get("red") or not t.get("green"): errors.append(f"{s['id']}: task lacks red/green")
for e in epics:
    for d in e["deps"]:
        if d not in E: errors.append(f"{e['id']}: missing epic dep {d}")
# story deps must respect epic deps (cross-epic deps only to declared/own epics)
for s in stories:
    ep = epic_of(s["id"])
    for d in s["deps"]:
        de = epic_of(d)
        if de != ep and de not in E[ep]["deps"]:
            errors.append(f"{s['id']} depends on {d} but {ep} does not declare {de}")
# cycle check + waves
indeg = {k: 0 for k in S}; children = defaultdict(list)
for s in stories:
    for d in s["deps"]:
        indeg[s["id"]] += 1; children[d].append(s["id"])
wave = {}; q = deque([k for k, v in indeg.items() if v == 0])
for k in q: wave[k] = 1
order = []
while q:
    n = q.popleft(); order.append(n)
    for c in children[n]:
        wave[c] = max(wave.get(c, 1), wave[n] + 1)
        indeg[c] -= 1
        if indeg[c] == 0: q.append(c)
if len(order) != len(S): errors.append("dependency cycle detected")
if errors:
    print("\n".join(errors)); sys.exit(1)

blocks = defaultdict(list)
for s in stories:
    for d in s["deps"]: blocks[d].append(s["id"])
by_epic = defaultdict(list)
for s in stories: by_epic[epic_of(s["id"])].append(s)

def slink(sid, frm):
    """relative link to a story from 'root' | 'epic' | 'story'"""
    ep = epic_of(sid); p = f"stories/{story_dir(ep)}/{story_file(sid)}"
    pre = {"root": "", "epic": "../", "story": "../../"}[frm]
    return f"[{sid}]({pre}{p})"
def elink(eid, frm):
    pre = {"root": "epics/", "epic": "", "story": "../../epics/"}[frm]
    return f"[{eid}]({pre}{epic_file(eid)})"

TASK_DOD = ["Red tests above committed before implementation and seen failing",
            "Tests pass; no skip/xfail added",
            "Changed-line coverage ≥ 90%; lint + type-check clean",
            "Refactor pass done with tests green"]
STORY_DOD = ["All tasks meet their Definition of Done",
             "All test cases below implemented and passing in CI",
             "Acceptance criteria demonstrated (CI output / recording linked in PR)",
             "Config, schema and contract changes documented and versioned",
             "No secrets or real personal data in repo or fixtures",
             "PR reviewed and merged; story status set to **Done**"]

OUT.mkdir(parents=True, exist_ok=True)
(OUT / "epics").mkdir(exist_ok=True)
tc_total = 0; tag_count = defaultdict(lambda: defaultdict(int)); guardrails = []

# ---- stories ----
for s in stories:
    sid = s["id"]; ep = epic_of(sid); num = sid[1:]
    d = OUT / "stories" / story_dir(ep); d.mkdir(parents=True, exist_ok=True)
    up = ", ".join(slink(x, "story") for x in s["deps"]) or "—"
    down = ", ".join(slink(x, "story") for x in sorted(blocks[sid])) or "—"
    L = [f"# {sid} — {s['title']}", "",
         "| Field | Value |", "|---|---|",
         f"| Epic | {elink(ep, 'story')} {E[ep]['name']} |",
         f"| Estimate | {s['pts']} pts |",
         f"| Build wave | {wave[sid]} |",
         f"| Status | {'Conditional — ' + s['condition'] if s.get('condition') else 'To do'} |",
         f"| Depends on | {up} |",
         f"| Blocks | {down} |", "",
         "## User story", "", s["story"], "",
         "## Context", "", s["context"], "",
         "## Acceptance criteria", ""]
    L += [f"- [ ] {a}" for a in s["ac"]]
    L += ["", "## Dependencies", ""]
    if s["deps"]:
        L += ["**Upstream (must be Done first):**", ""]
        L += [f"- {slink(x, 'story')} {S[x]['title']}" for x in s["deps"]]
    else:
        L += ["**Upstream:** none — can start immediately."]
    L += [""]
    if blocks[sid]:
        L += ["**Downstream (waiting on this story):**", ""]
        L += [f"- {slink(x, 'story')} {S[x]['title']}" for x in sorted(blocks[sid])]
    else:
        L += ["**Downstream:** none."]
    L += ["", "## Tasks", "", "Tasks run in the order listed; each starts with its Red step.", ""]
    for i, t in enumerate(s["tasks"], 1):
        tid = f"T{num}.{i}"
        tdeps = t.get("deps") or ([f"T{num}.{i-1}"] if i > 1 else (["upstream stories above"] if s["deps"] else ["none"]))
        L += [f"### {tid} — {t['t']}", "",
              f"**Depends on:** {', '.join(tdeps)}", "",
              "**Red — write these failing tests first:**", ""]
        L += [f"- `{r}`" if not r.startswith(("A ", "Metrics", "workflow")) else f"- {r}" for r in t["red"]]
        L += ["", f"**Green — implement:** {t['green']}", "",
              "**Refactor:** tidy names, remove duplication, keep tests green.", "",
              "**Definition of done:**", ""]
        L += [f"- [ ] {x}" for x in TASK_DOD + t.get("dod", [])]
        L += [""]
    L += ["## Test cases", "", "| ID | Type | Scenario |", "|---|---|---|"]
    for j, (tag, txt) in enumerate(s["tests"], 1):
        tcid = f"TC-{num}-{j:02d}"; tc_total += 1; tag_count[ep][tag] += 1
        if tag == "guardrail": guardrails.append((tcid, sid, txt))
        L.append(f"| {tcid} | `{tag}` | {txt.replace('|', '/')} |")
    L += ["", "Plus every Red test listed in the tasks above.", "",
          "## Definition of done", ""]
    L += [f"- [ ] {x}" for x in STORY_DOD + s.get("dod", [])]
    L += ["", "## Risks and notes", "", s.get("risks") or "None.", ""]
    (d / story_file(sid)).write_text("\n".join(L))

# ---- epics ----
for e in epics:
    eid = e["id"]; ss = by_epic[eid]
    L = [f"# {eid} — {e['name']}", "",
         "| Field | Value |", "|---|---|",
         f"| Depends on (epics) | {', '.join(elink(x, 'epic') for x in e['deps']) or '—'} |",
         f"| Stories | {len(ss)} |",
         f"| Estimate | {sum(s['pts'] for s in ss)} pts |",
         "| Status | To do |", "",
         "## Goal", "", e["goal"], "",
         "## Why it matters", "", e["why"], "",
         "## Scope", "", "**In scope:**", ""]
    L += [f"- {x}" for x in e["in_scope"]]
    L += ["", "**Out of scope:**", ""]
    L += [f"- {x}" for x in e["out_scope"]] or ["- —"]
    if not e["out_scope"]: L.append("- —")
    L += ["", "## Stories", "", "| Story | Title | Pts | Wave | Depends on |", "|---|---|---|---|---|"]
    for s in ss:
        L.append(f"| {slink(s['id'], 'epic')} | {s['title']}{' *(conditional)*' if s.get('condition') else ''} | {s['pts']} | {wave[s['id']]} | {', '.join(s['deps']) or '—'} |")
    L += ["", "## Story dependency graph", "", "```mermaid", "graph LR"]
    ids = {s["id"] for s in ss}
    for s in ss:
        L.append(f'  {s["id"].replace(".", "_")}["{s["id"]} {s["title"][:34]}"]')
    ext = set()
    for s in ss:
        for d in s["deps"]:
            if d not in ids: ext.add(d)
            L.append(f"  {d.replace('.', '_')} --> {s['id'].replace('.', '_')}")
    for x in sorted(ext):
        L.append(f'  {x.replace(".", "_")}(["{x} (other epic)"]):::ext')
    L += ["  classDef ext fill:#eee,stroke:#999,color:#555", "```", "",
          "## Test coverage by type", "", "| Type | Story-level test cases |", "|---|---|"]
    for tag, n in sorted(tag_count[eid].items()): L.append(f"| `{tag}` | {n} |")
    L += ["", "## Exit criteria", ""]
    L += [f"- [ ] {x}" for x in e["exit"]]
    L += ["", "## Definition of done (epic)", "",
          "- [ ] All stories Done", "- [ ] Exit criteria above met",
          "- [ ] Integration suite green on `main`", "- [ ] Docs/runbook section written",
          "- [ ] 5-minute demo to Doc", ""]
    (OUT / "epics" / epic_file(eid)).write_text("\n".join(L))

# ---- index ----
L = ["# JobOps — Index, dependency graph and traceability", "",
     f"{len(epics)} epics · {len(stories)} stories · "
     f"{sum(len(s['tasks']) for s in stories)} tasks · {tc_total} story-level test cases "
     f"(plus each task's Red tests) · {sum(s['pts'] for s in stories)} points", "",
     "See [PLAN.md](PLAN.md) for architecture, TDD strategy and the global Definition of Done.", "",
     "## Epics", "", "| Epic | Name | Stories | Pts | Depends on |", "|---|---|---|---|---|"]
for e in epics:
    ss = by_epic[e["id"]]
    L.append(f"| {elink(e['id'], 'root')} | {e['name']} | {len(ss)} | {sum(s['pts'] for s in ss)} | {', '.join(e['deps']) or '—'} |")
L += ["", "## Epic dependency graph", "", "```mermaid", "graph LR"]
for e in epics:
    L.append(f'  {e["id"]}["{e["id"]} {e["name"][:30]}"]')
    for d in e["deps"]: L.append(f"  {d} --> {e['id']}")
L += ["```", "", "## Build waves (story-level topological order)", "",
      "A story's wave = 1 + the highest wave of its dependencies. Everything in a wave can be built in parallel.", "",
      "| Wave | Stories |", "|---|---|"]
for w in sorted(set(wave.values())):
    L.append(f"| {w} | {', '.join(slink(k, 'root') for k in order if wave[k] == w)} |")
# critical path (longest by points)
best = {}; prev = {}
for k in order:
    base = max(((best[d], d) for d in S[k]["deps"]), default=(0, None))
    best[k] = base[0] + S[k]["pts"]; prev[k] = base[1]
end = max(best, key=best.get); path = []
while end: path.append(end); end = prev[end]
L += ["", f"## Critical path ({best[path[0]]} pts)", "", " → ".join(slink(k, "root") for k in reversed(path)), ""]
L += ["## All stories", "", "| Story | Title | Epic | Pts | Wave | Depends on | Blocks |", "|---|---|---|---|---|---|---|"]
for s in stories:
    L.append(f"| {slink(s['id'], 'root')} | {s['title']} | {epic_of(s['id'])} | {s['pts']} | {wave[s['id']]} | "
             f"{', '.join(s['deps']) or '—'} | {', '.join(sorted(blocks[s['id']])) or '—'} |")
L += ["", "## Test traceability by epic and type", ""]
tags = sorted({t for e in tag_count.values() for t in e})
L += ["| Epic | " + " | ".join(f"`{t}`" for t in tags) + " |", "|---" * (len(tags) + 1) + "|"]
for e in epics:
    L.append(f"| {e['id']} | " + " | ".join(str(tag_count[e['id']].get(t, 0)) for t in tags) + " |")
L += ["", "## Guardrail (release-blocking) test cases", "",
      "These form the S11.3 release gate. Any failure blocks merge to `main`.", "",
      "| Test | Story | Scenario |", "|---|---|---|"]
for tcid, sid, txt in guardrails:
    L.append(f"| {tcid} | {slink(sid, 'root')} | {txt.replace('|', '/')} |")
L += ["", "## Agent → story map", "",
      "| Agent | Primary stories |", "|---|---|",
      "| Manager | " + ", ".join(slink(x, 'root') for x in ["S05.1", "S05.2", "S05.3", "S05.4", "S05.5", "S10.4"]) + " |",
      "| Scout | " + ", ".join(slink(x, 'root') for x in ["S06.1", "S06.2", "S06.3", "S06.4", "S02.6", "S03.3", "S03.7"]) + " |",
      "| Tailor | " + ", ".join(slink(x, 'root') for x in ["S07.1", "S07.2", "S07.3", "S07.4", "S03.4", "S03.5"]) + " |",
      "| Critic | " + ", ".join(slink(x, 'root') for x in ["S08.1", "S08.2", "S08.3", "S08.4", "S08.5"]) + " |",
      "| Concierge | " + ", ".join(slink(x, 'root') for x in ["S09.1", "S09.2", "S09.3", "S09.4", "S09.5", "S09.6"]) + " |", ""]
(OUT / "00-INDEX.md").write_text("\n".join(L))
print(f"OK: {len(epics)} epics, {len(stories)} stories, {sum(len(s['tasks']) for s in stories)} tasks, {tc_total} TCs, "
      f"{len(guardrails)} guardrails, waves={max(wave.values())}, critical={best[path[0]]}pts")
