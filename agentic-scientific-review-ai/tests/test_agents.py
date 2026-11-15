import pytest
from reviewai.provider import DemoProvider
from reviewai.agents import plan,strategy,validate_protocol,screen,prisma_counts,extract,critic


def test_protocol_has_required_fields():
    p=plan(DemoProvider(),"Lakehouse analytics",12)
    validate_protocol(p)
    assert p["databases"]==["Synthetic fixture only (NO real literature searches)"]
    assert len(strategy(DemoProvider(),p))==2


def test_protocol_invalid():
    with pytest.raises(ValueError): validate_protocol({})


def test_screen_independent_records():
    p=plan(DemoProvider(),"Lakehouse analytics",5)
    paper={"id":"X","title":"Lakehouse query scalability","abstract":"An experiment on scalable systems","full_text":"A lakehouse test"}
    decisions=screen(DemoProvider(),[paper],p,"title")
    assert decisions[0]["decision"]=="include"
    assert len(decisions[0]["reviewers"])==2


def test_missing_fulltext_not_included():
    p=plan(DemoProvider(),"Lakehouse analytics",5)
    paper={"id":"X","title":"Lakehouse query scalability","abstract":"Relevant architecture","full_text":""}
    d=screen(DemoProvider(),[paper],p,"fulltext")[0]
    assert d["decision"]=="not_assessed_missing_fulltext"
    with pytest.raises(ValueError): extract(DemoProvider(),paper)


def test_prisma_consistency(demo_state):
    counts=demo_state["prisma"]
    assert counts["records_identified"]==7
    assert counts["duplicates_removed"]==1
    assert counts["records_title_screened"]==6
    assert counts["reports_not_retrieved"]==1
    assert counts["studies_included"]==3
    assert counts["reports_sought_for_retrieval"]==4


def test_critic_expected_checks(demo_state):
    qa=critic(demo_state)
    assert qa["passed"]==qa["total"]
    assert qa["needs_human_validation"] is True
    assert any("SYNTHETIC" in s for s in qa["caveats"])
