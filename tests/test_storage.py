import pytest
from reviewai.storage import Store


def test_create_load_and_version(tmp_path):
    s=Store(tmp_path)
    state=s.create("A sufficiently long research question","demo")
    before=s.get(state["run_id"])
    assert before["version"]==1
    state["protocol"]={"research_question":"Q"}
    s.save(state,"awaiting_approval")
    after=s.get(state["run_id"])
    assert after["status"]=="awaiting_approval" and after["version"]==2
    assert len(s.events(state["run_id"]))==1


def test_approval_rejects_changed_protocol(engine):
    s=engine.prepare("A sufficiently long lakehouse research question for science","demo")
    changed=dict(s["protocol"])
    changed["objective"]="New objective"
    with pytest.raises(ValueError):
        engine.store.approve(s["run_id"],changed)
    engine.store.approve(s["run_id"])
    assert engine.store.get(s["run_id"])["approved"]


def test_override_is_auditable(engine):
    s=engine.prepare("A sufficiently long lakehouse research question for science","demo")
    paper=s["papers"][0]
    with pytest.raises(ValueError):
        engine.store.override(s["run_id"],paper["id"],"include","")
    engine.store.override(s["run_id"],paper["id"],"exclude","Human disagrees with simulated screening")
    assert engine.store.overrides(s["run_id"])[paper["id"]]["decision"]=="exclude"
    assert any(e["stage"]=="human_screening_override" for e in engine.store.events(s["run_id"]))


def test_reject_unknown_override(engine):
    s=engine.prepare("A sufficiently long lakehouse research question for science","demo")
    with pytest.raises(ValueError):
        engine.store.override(s["run_id"],"NOTREAL","include","some rationale")
