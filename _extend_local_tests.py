from pathlib import Path

p = Path(r"C:\abrasax\tests\test_local_first_routing.py")
s = p.read_text(encoding="utf-8")

extra = '''

# ---- the supervisor publishes the decision ---------------------------------

SUP = Path(__file__).resolve().parents[1] / "SCRIPTS" / "automation" / "supervisor.py"


def test_snapshot_writes_a_usable_state_file(monkeypatch, tmp_path):
    state = tmp_path / "llm-mode.json"
    monkeypatch.setattr(autonomy, "STATE", state)
    out = autonomy.snapshot(up_ids=["lmstudio"], write_state=True)
    data = json.loads(state.read_text(encoding="utf-8"))
    assert data["mode"] == "local_only"
    assert data["paid_allowed"] is False
    assert data["local_up"] == ["lmstudio"]
    assert data["ts"] == out["ts"]


def test_the_supervisor_computes_the_mode_after_the_liveness_it_uses():
    src = SUP.read_text(encoding="utf-8")
    assert "autonomy.snapshot(up_ids=up_ids" in src
    i_up = src.index('up_ids = {e["svc"]')
    i_call = src.index("autonomy.snapshot(up_ids=up_ids")
    i_summary = src.index("summary = {", i_up)
    assert i_up < i_call < i_summary, "autonomy must run between up_ids and summary"
    assert '"llm_mode": (_llm_mode or {}).get("mode")' in src


def test_a_tick_that_cannot_write_the_mode_does_not_die():
    src = SUP.read_text(encoding="utf-8")
    start = src.index("from abrasax import autonomy")
    block = src[start:start + 600]
    assert "except Exception" in block and "autonomy_error" in block
'''

anchor = "\ndef test_a_local_answer_is_preferred_and_never_escalates(monkeypatch):"
assert anchor in s
s = s.replace(anchor, extra + anchor, 1)
p.write_text(s, encoding="utf-8", newline="")
print("tests extended")
