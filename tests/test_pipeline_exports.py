import json
import pytest
from pathlib import Path
from reviewai.evaluation import evaluate
from reviewai.exports import make_report,prisma_svg,export_run,zip_outputs
from reviewai.cli import main


def test_demo_end_to_end(demo_state,engine):
    assert demo_state["mode"]=="demo"
    assert demo_state["runtime"] in {"langgraph","offline-sequential-demo-fallback"}
    assert len(demo_state["extractions"])==3
    assert all(x["evidence_supported"] for x in demo_state["extractions"])
    assert len(demo_state["rag_hits"])>=1
    assert demo_state["quality_assurance"]["passed"]==demo_state["quality_assurance"]["total"]
    assert engine.store.get(demo_state["run_id"])["status"]=="completed"


def test_must_approve(engine):
    state=engine.prepare("Review of scalable lakehouse architectures","demo")
    with pytest.raises(PermissionError):
        engine.continue_review(state["run_id"])


def test_human_override_applied(engine):
    state=engine.prepare("Review of scalable lakehouse architectures","demo")
    id0="SYN-001"
    engine.store.override(state["run_id"],id0,"exclude","Human manual exclusion")
    done=engine.continue_review(state["run_id"],approve=True)
    assert any(d["paper_id"]==id0 and d["decision"]=="exclude" and d["human_override"] for d in done["title_screen"])
    assert id0 not in {e["paper_id"] for e in done["extractions"]}


def test_cannot_double_complete(engine):
    state=engine.prepare("Review of scalable lakehouse architectures","demo")
    engine.continue_review(state["run_id"],approve=True)
    with pytest.raises(ValueError):engine.continue_review(state["run_id"])


def test_outputs_created(demo_state,engine):
    folder=engine.store.output_dir(demo_state["run_id"])
    for filename in ("systematic_review.md","references.bib","prisma_flow.svg",
                     "title_screening.csv","fulltext_screening.csv","evidence_table.csv",
                     "audit_trail.json","manifest.json","rag/chunks.json","rag/vectors.npy"):
        assert (folder/filename).exists(),filename
    content=(folder/"systematic_review.md").read_text()
    assert "SYNTHETIC" in content and "PRISMA" in content
    assert b"systematic_review.md" in zip_outputs(folder)
    assert "<svg" in prisma_svg(demo_state["prisma"])


def test_evaluation_fixture_only(demo_state):
    fixture=Path(__file__).resolve().parents[1]/"fixtures"/"demo_papers.json"
    result=evaluate(demo_state,fixture_file=fixture)
    assert result["benchmark_type"]=="synthetic_only"
    assert result["screening_gold_records"]==6
    assert result["screening_f1"]==1.0
    assert result["time_saving_percent"] is None


def test_evaluation_manual_not_assumed(demo_state):
    result=evaluate(demo_state)
    assert result["manual_baseline_minutes"] is None
    assert result["screening_precision"] is None


def test_cli_demo_offline(tmp_path):
    exitcode=main(["--data-dir",str(tmp_path),"demo"])
    assert exitcode==0
    assert list((tmp_path/"runs").glob("*/evaluation.json"))


def test_report_references_only_included(demo_state):
    content=make_report(demo_state)
    assert "[SYN-001]" in content
    assert "[SYN-004]" not in content


def test_human_gold_csv_evaluation(demo_state,tmp_path):
    gold=tmp_path/"reference.csv"
    gold.write_text("paper_id,human_label\nSYN-001,include\nSYN-002,include\nSYN-004,exclude\n",encoding="utf-8")
    result=evaluate(demo_state,gold_csv=gold)
    assert result["benchmark_type"]=="human_gold_csv"
    assert result["screening_gold_records"]==3
    assert result["screening_f1"]==1
    assert result["inter_agent_cohen_kappa"]==1


def test_bad_gold_labels_rejected(demo_state,tmp_path):
    gold=tmp_path/"reference.csv"
    gold.write_text("paper_id,human_label\nSYN-001,maybe\n",encoding="utf-8")
    with pytest.raises(ValueError):evaluate(demo_state,gold_csv=gold)


def test_demo_prevents_topic_mismatch(engine):
    with pytest.raises(ValueError,match="only supports lakehouse"):
        engine.prepare("A systematic review of proteomics and AI","demo")
