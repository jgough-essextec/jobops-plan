"""Tests for tools/build_state.py — written before the tool (TDD)."""
import subprocess, sys, textwrap
from pathlib import Path
import pytest

_here = Path(__file__).resolve().parents[1]
# works in the kit (kit/tools/build_state.py) and in the repo (plan/tools/build_state.py)
TOOL = next(p for p in (_here / "build_state.py", _here / "tools" / "build_state.py") if p.exists())
sys.path.insert(0, str(TOOL.parent))
import build_state as bs  # noqa: E402


@pytest.fixture
def plan(tmp_path):
    src = tmp_path / "_source"; src.mkdir()
    (src / "stories_x.yaml").write_text(textwrap.dedent("""
        - {id: S00.1, title: A, deps: []}
        - {id: S00.2, title: B, deps: [S00.1]}
        - {id: S00.3, title: C, deps: [S00.1]}
        - {id: S01.1, title: D, deps: [S00.2, S00.3]}
        - {id: S01.2, title: E, deps: [S01.1], condition: "only if path B"}
    """))
    (tmp_path / "checkpoints.yaml").write_text(textwrap.dedent("""
        - {id: S00.3, when: before, ask: "Provide token"}
        - {id: S00.2, when: after, ask: "Review spike"}
    """))
    return tmp_path


def state(plan):
    return bs.BuildState.load(plan)


def test_init_creates_status_with_all_todo(plan):
    s = state(plan)
    assert set(s.status) == {"S00.1", "S00.2", "S00.3", "S01.1", "S01.2"}
    assert all(v == "todo" for v in s.status.values())
    assert (plan / "status.yaml").exists()


def test_next_returns_only_stories_with_done_deps(plan):
    s = state(plan)
    assert s.next_ready() == ["S00.1"]
    s.start("S00.1"); s.done("S00.1")
    # S00.3 needs a 'before' checkpoint → not ready until cleared
    assert s.next_ready() == ["S00.2"]


def test_before_checkpoint_blocks_until_cleared(plan):
    s = state(plan); s.start("S00.1"); s.done("S00.1")
    assert "S00.3" in s.pending_before()
    s.clear_checkpoint("S00.3")
    assert s.next_ready() == ["S00.2", "S00.3"]


def test_after_checkpoint_moves_to_waiting_on_doc(plan):
    s = state(plan); s.start("S00.1"); s.done("S00.1")
    s.start("S00.2"); s.done("S00.2")
    assert s.status["S00.2"] == "waiting_on_doc"
    s.clear_checkpoint("S00.2")
    assert s.status["S00.2"] == "done"


def test_cannot_start_story_with_unfinished_deps(plan):
    s = state(plan)
    with pytest.raises(bs.BuildError, match="S00.1"):
        s.start("S00.2")


def test_cannot_finish_story_not_in_progress(plan):
    s = state(plan)
    with pytest.raises(bs.BuildError):
        s.done("S00.1")


def test_wont_do_satisfies_dependency(plan):
    s = state(plan)
    for sid in ["S00.1"]:
        s.start(sid); s.done(sid)
    s.clear_checkpoint("S00.2"); s.clear_checkpoint("S00.3")
    for sid in ["S00.2", "S00.3"]:
        s.start(sid); s.done(sid)
    s.start("S01.1"); s.done("S01.1")
    s.wont_do("S01.2", "path A chosen")
    assert s.status["S01.2"] == "wont_do"
    assert s.all_finished()


def test_block_records_reason_and_excludes_from_next(plan):
    s = state(plan); s.start("S00.1"); s.block("S00.1", "LiteLLM down")
    assert s.status["S00.1"] == "blocked"
    assert s.next_ready() == []
    assert s.notes["S00.1"] == "LiteLLM down"


def test_state_persists_between_loads(plan):
    s = state(plan); s.start("S00.1"); s.done("S00.1")
    assert state(plan).status["S00.1"] == "done"


def test_unknown_story_rejected(plan):
    with pytest.raises(bs.BuildError, match="unknown"):
        state(plan).start("S99.9")


def test_report_lists_counts_and_checkpoints(plan):
    md = state(plan).report()
    assert "todo: 5" in md and "S00.3" in md and "Provide token" in md


def test_cli_next_prints_ids(plan):
    out = subprocess.run([sys.executable, str(TOOL), "--plan", str(plan), "next"],
                         capture_output=True, text=True, check=True).stdout
    assert out.strip() == "S00.1"


def test_cli_error_exit_code(plan):
    r = subprocess.run([sys.executable, str(TOOL), "--plan", str(plan), "start", "S00.2"],
                       capture_output=True, text=True)
    assert r.returncode == 2 and "S00.1" in r.stderr
