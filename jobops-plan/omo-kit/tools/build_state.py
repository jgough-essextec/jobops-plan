#!/usr/bin/env python3
"""JobOps build state — tells the coding agent which story to build next.

Reads story dependencies from <plan>/_source/stories_*.yaml and human checkpoints from
<plan>/checkpoints.yaml; keeps progress in <plan>/status.yaml.

Statuses: todo · in_progress · done · waiting_on_doc · blocked · wont_do

  python tools/build_state.py next            # stories ready to start (deps done, no pending checkpoint)
  python tools/build_state.py start S02.3
  python tools/build_state.py done S02.3      # → waiting_on_doc if the story has an 'after' checkpoint
  python tools/build_state.py block S02.3 "reason"
  python tools/build_state.py wont-do S10.7 "ADR-9 chose path B"
  python tools/build_state.py report          # markdown summary incl. what Doc needs to do
  python tools/build_state.py clear S09.1     # DOC ONLY: clears a checkpoint
"""
from __future__ import annotations
import argparse, glob, sys
from pathlib import Path
import yaml

SATISFIED = {"done", "wont_do"}


class BuildError(Exception):
    pass


class BuildState:
    def __init__(self, plan: Path, stories: dict, checkpoints: dict, status: dict, cleared: list, notes: dict):
        self.plan, self.stories, self.checkpoints = plan, stories, checkpoints
        self.status, self.cleared, self.notes = status, cleared, notes

    # ---------- loading / saving ----------
    @classmethod
    def load(cls, plan: Path | str) -> "BuildState":
        plan = Path(plan)
        stories = {}
        for f in sorted(glob.glob(str(plan / "_source" / "stories_*.yaml"))):
            for s in yaml.safe_load(Path(f).read_text()) or []:
                stories[s["id"]] = s
        if not stories:
            raise BuildError(f"no stories found under {plan / '_source'}")
        cp_file = plan / "checkpoints.yaml"
        checkpoints = {c["id"]: c for c in (yaml.safe_load(cp_file.read_text()) or [])} if cp_file.exists() else {}
        st_file = plan / "status.yaml"
        data = yaml.safe_load(st_file.read_text()) if st_file.exists() else {}
        data = data or {}
        status = {sid: (data.get("stories") or {}).get(sid, "todo") for sid in stories}
        self = cls(plan, stories, checkpoints, status, list(data.get("checkpoints_cleared") or []),
                   dict(data.get("notes") or {}))
        self.save()
        return self

    def save(self) -> None:
        (self.plan / "status.yaml").write_text(yaml.safe_dump(
            {"stories": self.status, "checkpoints_cleared": self.cleared, "notes": self.notes}, sort_keys=True))

    # ---------- queries ----------
    def _check(self, sid: str) -> None:
        if sid not in self.stories:
            raise BuildError(f"unknown story {sid}")

    def _deps_open(self, sid: str) -> list[str]:
        return [d for d in self.stories[sid].get("deps", []) if self.status.get(d) not in SATISFIED]

    def _before_pending(self, sid: str) -> bool:
        cp = self.checkpoints.get(sid)
        return bool(cp and cp.get("when") == "before" and sid not in self.cleared)

    def next_ready(self) -> list[str]:
        return [sid for sid in self.stories
                if self.status[sid] == "todo" and not self._deps_open(sid) and not self._before_pending(sid)]

    def pending_before(self) -> list[str]:
        return [sid for sid in self.stories
                if self.status[sid] == "todo" and not self._deps_open(sid) and self._before_pending(sid)]

    def all_finished(self) -> bool:
        return all(v in SATISFIED for v in self.status.values())

    # ---------- transitions ----------
    def start(self, sid: str) -> None:
        self._check(sid)
        if self.status[sid] not in ("todo", "blocked"):
            raise BuildError(f"{sid} is {self.status[sid]}, cannot start")
        if open_ := self._deps_open(sid):
            raise BuildError(f"{sid} waits on unfinished dependencies: {', '.join(open_)}")
        if self._before_pending(sid):
            raise BuildError(f"{sid} needs Doc first: {self.checkpoints[sid]['ask']}")
        self.status[sid] = "in_progress"; self.notes.pop(sid, None); self.save()

    def done(self, sid: str) -> None:
        self._check(sid)
        if self.status[sid] != "in_progress":
            raise BuildError(f"{sid} is {self.status[sid]}, only in_progress stories can be finished")
        cp = self.checkpoints.get(sid)
        needs_review = cp and cp.get("when") == "after" and sid not in self.cleared
        self.status[sid] = "waiting_on_doc" if needs_review else "done"; self.save()

    def block(self, sid: str, reason: str) -> None:
        self._check(sid); self.status[sid] = "blocked"; self.notes[sid] = reason; self.save()

    def wont_do(self, sid: str, reason: str) -> None:
        self._check(sid); self.status[sid] = "wont_do"; self.notes[sid] = reason; self.save()

    def clear_checkpoint(self, sid: str) -> None:
        self._check(sid)
        if sid not in self.cleared:
            self.cleared.append(sid)
        if self.status[sid] == "waiting_on_doc":
            self.status[sid] = "done"
        self.save()

    # ---------- report ----------
    def report(self) -> str:
        counts: dict[str, int] = {}
        for v in self.status.values():
            counts[v] = counts.get(v, 0) + 1
        L = ["# JobOps build status", "", " · ".join(f"{k}: {n}" for k, n in sorted(counts.items())), "",
             "## Ready to build", ""] + [f"- {s} {self.stories[s]['title']}" for s in self.next_ready()] + [""]
        doc = [(s, self.checkpoints[s]["ask"]) for s in self.pending_before()]
        doc += [(s, self.checkpoints[s]["ask"]) for s, v in self.status.items() if v == "waiting_on_doc"]
        L += ["## Waiting on Doc", ""] + ([f"- **{s}**: {a}" for s, a in doc] or ["- nothing"]) + [""]
        upcoming = [s for s, c in self.checkpoints.items() if self.status[s] == "todo" and s not in self.cleared
                    and s not in dict(doc)]
        L += ["## Later checkpoints", ""] + ([f"- {s} ({self.checkpoints[s]['when']}): {self.checkpoints[s]['ask']}"
                                               for s in upcoming] or ["- none"]) + [""]
        blocked = [s for s, v in self.status.items() if v == "blocked"]
        L += ["## Blocked", ""] + ([f"- {s}: {self.notes.get(s, '')}" for s in blocked] or ["- none"]) + [""]
        return "\n".join(L)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--plan", default="plan", help="plan directory (default: ./plan)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("next"); sub.add_parser("report"); sub.add_parser("finished")
    for c in ("start", "done", "clear"):
        sub.add_parser(c).add_argument("sid")
    for c in ("block", "wont-do"):
        sp = sub.add_parser(c); sp.add_argument("sid"); sp.add_argument("reason")
    a = p.parse_args(argv)
    try:
        s = BuildState.load(a.plan)
        if a.cmd == "next": print("\n".join(s.next_ready()))
        elif a.cmd == "report": print(s.report())
        elif a.cmd == "finished": print("yes" if s.all_finished() else "no"); return 0 if s.all_finished() else 1
        elif a.cmd == "start": s.start(a.sid)
        elif a.cmd == "done": s.done(a.sid); print(s.status[a.sid])
        elif a.cmd == "clear": s.clear_checkpoint(a.sid)
        elif a.cmd == "block": s.block(a.sid, a.reason)
        elif a.cmd == "wont-do": s.wont_do(a.sid, a.reason)
    except BuildError as e:
        print(f"error: {e}", file=sys.stderr); return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
