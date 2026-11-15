"""Streamlit UI for explicit two-phase human-in-the-loop review."""
from __future__ import annotations
import json
import os
from pathlib import Path
import streamlit as st
from dotenv import load_dotenv
from reviewai.config import Settings
from reviewai.pipeline import ReviewEngine
from reviewai.exports import zip_outputs
from reviewai.evaluation import evaluate

load_dotenv()
st.set_page_config(page_title="Agentic Scientific Review AI",page_icon="📚",layout="wide")
st.title("Agentic Scientific Review AI")
st.caption("LangGraph + Gemini + hybrid RAG · PRISMA-aligned teaching/research prototype")
engine=ReviewEngine(Settings())

with st.sidebar:
    st.subheader("Mode & environment")
    mode=st.radio("Execution mode",["demo","live"],
                  format_func=lambda x:"Synthetic offline demo (no Gemini)" if x=="demo" else "Live Gemini + academic APIs")
    st.warning("Synthetic mode uses FABRICATED sample studies and rule-based decisions, not genuine research.") if mode=="demo" else None
    st.info("Gemini API key configured" if bool(os.getenv("GEMINI_API_KEY")) else "Set GEMINI_API_KEY in .env for live mode")
    st.caption(f"Persistent storage: {Settings().data_dir.resolve()}")
    st.divider()
    st.subheader("Existing review runs")
    choices=engine.store.list_runs()
    for item in choices[:15]:
        if st.button(f"{item['id']} · {item['status']} · {item['topic'][:28]}",key="load-"+item["id"]):
            st.session_state["run_id"]=item["id"]
            st.rerun()

st.subheader("1 · Create a review")
topic=st.text_input("Scientific topic or research question",
                    value="Scalable lakehouse architectures for big data analytics")
max_papers=st.slider("Maximum unique papers (live mode)",min_value=2,max_value=50,value=12)
if st.button("Generate protocol, search and title-screen",type="primary"):
    try:
        with st.spinner("Planning, searching and screening ..."):
            state=engine.prepare(topic,mode,max_papers)
        st.session_state["run_id"]=state["run_id"]
        st.success("Preparation complete. Human review and approval required.")
        st.rerun()
    except Exception as exc:
        st.error(f"Could not prepare review: {exc}")

run_id=st.session_state.get("run_id")
if run_id:
    try:
        record=engine.store.get(run_id)
    except KeyError:
        st.error("Run not found")
        st.stop()
    s=record["state"]
    st.divider()
    st.subheader(f"2 · Review {run_id} — {record['status']}")
    st.json(s.get("protocol",{}),expanded=False)
    if s.get("queries"):
        st.write("**Search queries:**", " · ".join(s["queries"]))
    if s.get("search_events"):
        with st.expander("Source-by-source search log"):
            st.json(s["search_events"])
    if s.get("title_screen"):
        rows=[]
        for decision in s["title_screen"]:
            paper=next(p for p in s["papers"] if p["id"]==decision["paper_id"])
            rows.append({"id":paper["id"],"paper":paper["title"],"decision":decision["decision"],
                         "disagreement":decision["conflict"],"rationale":decision["rationale"]})
        st.dataframe(rows,use_container_width=True,hide_index=True)
    if record["status"]=="awaiting_approval":
        st.markdown("**Optional: override a screening decision with a justification**")
        ids=[p["id"] for p in s["papers"]]
        with st.form("override_form"):
            pid=st.selectbox("Paper ID",ids)
            decision=st.selectbox("Human decision",["include","exclude","uncertain"])
            rationale=st.text_input("Justification for override")
            if st.form_submit_button("Save override"):
                try:
                    engine.store.override(run_id,pid,decision,rationale)
                    st.success("Override recorded in audit trail")
                except Exception as exc:
                    st.error(str(exc))
        overrides=engine.store.overrides(run_id)
        if overrides:
            st.json(overrides,expanded=False)
        confirmed=st.checkbox("I have reviewed the protocol and screening decisions and approve continuation",value=False)
        if st.button("Approve and finish full-text review",disabled=not confirmed,type="primary"):
            try:
                with st.spinner("Retrieving eligible full texts, extracting evidence, indexing RAG and synthesizing ..."):
                    engine.continue_review(run_id,approve=True)
                st.success("Review completed; inspect QA caveats and exported artifacts.")
                st.rerun()
            except Exception as exc:
                st.error(f"Completion failed: {exc}")
    if record["status"]=="completed":
        qa=s["quality_assurance"]
        st.subheader("3 · Results, quality checks and exports")
        a,b,c=st.columns(3)
        a.metric("Papers screened",s["prisma"]["records_title_screened"])
        b.metric("Full-text studies included",s["prisma"]["studies_included"])
        c.metric("Automated checks",f"{qa['passed']}/{qa['total']}")
        for caveat in qa["caveats"]:
            st.warning(caveat)
        st.markdown((engine.store.output_dir(run_id)/"systematic_review.md").read_text(encoding="utf-8"))
        if s["mode"]=="demo":
            fixture=Path(__file__).resolve().parent/"fixtures"/"demo_papers.json"
            st.json(evaluate(s,fixture_file=fixture),expanded=False)
        output=engine.store.output_dir(run_id)
        st.download_button("Download review artifacts ZIP",zip_outputs(output),
                           file_name=f"review-{run_id}.zip",mime="application/zip")
    with st.expander("Chronological audit event history"):
        st.json(engine.store.events(run_id))
