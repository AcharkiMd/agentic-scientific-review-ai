"""Honest evaluation: synthetic fixture metrics and optional measured manual baseline."""
from __future__ import annotations
import json
import csv
from pathlib import Path
from typing import Any


def evaluate(state: dict, fixture_file: Path | None = None,
             manual_minutes: float | None = None,
             gold_csv: Path | None = None) -> dict:
    predictions={d["paper_id"]:d["decision"] for d in state.get("title_screen",[])}
    if gold_csv is not None and fixture_file is not None:
        raise ValueError("Choose either fixture_file or human gold_csv, not both")
    if gold_csv is not None:
        with gold_csv.open(encoding="utf-8-sig",newline="") as handle:
            labels={r["paper_id"].strip():r["human_label"].strip().lower()
                    for r in csv.DictReader(handle)
                    if r.get("paper_id") and r.get("human_label")}
        if any(x not in {"include","exclude"} for x in labels.values()):
            raise ValueError("Human labels must be include or exclude")
    elif fixture_file:
        raw=json.loads(fixture_file.read_text(encoding="utf-8"))["papers"]
        # Deduplicate benchmark ground truth using the same title/year+DOI logic as retrieval.
        from .sources import deduplicate
        unique,_=deduplicate(raw)
        labels={p["id"]: next((r["gold_label"] for r in raw if r["id"]==p["id"]),None)
                for p in unique}
    else:
        labels={}
    ids=[pid for pid in labels if pid in predictions and labels[pid] in ("include","exclude")]
    tp=sum(labels[pid]=="include" and predictions[pid]=="include" for pid in ids)
    fp=sum(labels[pid]=="exclude" and predictions[pid]=="include" for pid in ids)
    fn=sum(labels[pid]=="include" and predictions[pid]!="include" for pid in ids)
    tn=sum(labels[pid]=="exclude" and predictions[pid]=="exclude" for pid in ids)
    precision=tp/(tp+fp) if tp+fp else 0.0
    recall=tp/(tp+fn) if tp+fn else 0.0
    f1=2*precision*recall/(precision+recall) if precision+recall else 0.0
    decisions=state.get("title_screen",[])
    comparable=[d for d in decisions if len(d.get("reviewers",[]))==2]
    agreement=sum(d["reviewers"][0]["decision"]==d["reviewers"][1]["decision"]
                  for d in comparable)/len(comparable) if comparable else None
    kappa=None
    if comparable:
        labels_set={"include","exclude","uncertain"}
        prob1={lab:sum(d["reviewers"][0]["decision"]==lab for d in comparable)/len(comparable) for lab in labels_set}
        prob2={lab:sum(d["reviewers"][1]["decision"]==lab for d in comparable)/len(comparable) for lab in labels_set}
        expected=sum(prob1[lab]*prob2[lab] for lab in labels_set)
        if expected<1:
            kappa=(agreement-expected)/(1-expected)
    quote_rows=state.get("extractions",[])
    report={"mode":state.get("mode"),"benchmark_type":"human_gold_csv" if gold_csv else ("synthetic_only" if fixture_file else "no_ground_truth"),
            "screening_gold_records":len(ids),"true_positive":tp,"false_positive":fp,
            "false_negative":fn,"true_negative":tn,
            "screening_precision":round(precision,4) if ids else None,
            "screening_recall":round(recall,4) if ids else None,
            "screening_f1":round(f1,4) if ids else None,
            "inter_agent_agreement":round(agreement,4) if agreement is not None else None,
            "inter_agent_cohen_kappa":round(kappa,4) if kappa is not None else None,
            "quote_verbatim_fraction":round(sum(e.get("evidence_supported",False) for e in quote_rows)/len(quote_rows),4) if quote_rows else None,
            "qa_checks_passed":state.get("quality_assurance",{}).get("passed"),
            "qa_checks_total":state.get("quality_assurance",{}).get("total"),
            "automated_runtime_seconds":round(state.get("elapsed_seconds",0),3),
            "manual_baseline_minutes":manual_minutes,
            "time_saving_percent":None,
            "disclaimer":("Synthetic labels are a software unit-test fixture, NOT independent scientific accuracy validation. "
                          "Human expert-ground-truth evaluation must be performed for live reviews." if fixture_file
                          else "Accuracy from human labels is meaningful only when labels are independent, adjudicated and representative.")}
    if manual_minutes and manual_minutes>0:
        automation_minutes=state.get("elapsed_seconds",0)/60
        report["time_saving_percent"]=round(100*(manual_minutes-automation_minutes)/manual_minutes,2)
        report["manual_baseline_caveat"]="Time savings are meaningful only for comparable scope and independently measured manual work."
    return report
