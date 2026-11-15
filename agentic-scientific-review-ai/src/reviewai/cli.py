"""Command line entry point. Run `python -m reviewai.cli --help`."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from .config import Settings
from .evaluation import evaluate
from .exports import export_run
from .pipeline import ReviewEngine

DEFAULT_TOPIC="Scalable lakehouse architectures for big data analytics"


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(prog="reviewai",description="Agentic Scientific Review AI")
    parser.add_argument("--data-dir",default=None,help="SQLite/artifact path (default: ./data)")
    cmd=parser.add_subparsers(dest="command",required=True)
    demo=cmd.add_parser("demo",help="SYNTHETIC offline end-to-end test, NOT scientific results")
    demo.add_argument("--topic",default=DEFAULT_TOPIC)
    prep=cmd.add_parser("prepare",help="Plan, retrieve and screen, then await human approval")
    prep.add_argument("--topic",required=True)
    prep.add_argument("--mode",choices=["demo","live"],default="live")
    prep.add_argument("--max-papers",type=int,default=12)
    resume=cmd.add_parser("continue",help="Continue a prepared review after explicit approval")
    resume.add_argument("run_id")
    resume.add_argument("--approve",action="store_true")
    override=cmd.add_parser("override",help="Human title-screening override before approval")
    override.add_argument("run_id")
    override.add_argument("paper_id")
    override.add_argument("decision",choices=["include","exclude","uncertain"])
    override.add_argument("--reason",required=True)
    cmd.add_parser("list",help="List available runs")
    stat=cmd.add_parser("status")
    stat.add_argument("run_id")
    ev=cmd.add_parser("evaluate")
    ev.add_argument("run_id")
    ev.add_argument("--gold-csv",type=Path,default=None,
                    help="CSV with paper_id,human_label columns (independent human reference)")
    ev.add_argument("--manual-minutes",type=float,default=None,
                    help="Measured manual baseline; OMIT if unavailable")
    ex=cmd.add_parser("export")
    ex.add_argument("run_id")
    args=parser.parse_args(argv)
    if args.data_dir:
        import os
        os.environ["REVIEWAI_DATA_DIR"] = args.data_dir
    engine=ReviewEngine(Settings())
    try:
        if args.command=="demo":
            state=engine.prepare(args.topic,"demo",max_papers=12)
            print("SYNTHETIC DEMO — auto-approval applies ONLY to this fabricated dataset.")
            state=engine.continue_review(state["run_id"],approve=True)
            result=evaluate(state,fixture_file=Path(__file__).resolve().parents[2]/"fixtures"/"demo_papers.json")
            out=engine.store.output_dir(state["run_id"])
            (out/"evaluation.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
            print(json.dumps({"run_id":state["run_id"],"mode":"SYNTHETIC DEMO",
                              "runtime":state["runtime"],"included":state["prisma"]["studies_included"],
                              "screening_f1_fixture_only":result["screening_f1"],
                              "outputs":str(out.resolve())},indent=2))
        elif args.command=="prepare":
            state=engine.prepare(args.topic,args.mode,args.max_papers)
            print(json.dumps({"run_id":state["run_id"],"status":"awaiting_approval",
                              "runtime":state["runtime"],"papers":len(state["papers"]),
                              "screening":state["title_screen"],
                              "next":"Inspect decisions, then reviewai continue RUN_ID --approve"},indent=2))
        elif args.command=="continue":
            state=engine.continue_review(args.run_id,approve=args.approve)
            print(json.dumps({"run_id":args.run_id,"status":"completed",
                              "included":state["prisma"]["studies_included"],
                              "qa":state["quality_assurance"]["checks"]},indent=2))
        elif args.command=="override":
            engine.store.override(args.run_id,args.paper_id,args.decision,args.reason)
            print("Saved audited human override")
        elif args.command=="list":
            print(json.dumps(engine.store.list_runs(),indent=2))
        elif args.command=="status":
            row=engine.store.get(args.run_id)
            print(json.dumps({"id":row["id"],"mode":row["mode"],"topic":row["topic"],
                              "status":row["status"],"approved":row["approved"],
                              "version":row["version"],"events":len(engine.store.events(args.run_id)),
                              "protocol":row["state"].get("protocol",{})},indent=2))
        elif args.command=="export":
            print(export_run(engine.store,args.run_id))
        elif args.command=="evaluate":
            state=engine.store.get(args.run_id)["state"]
            fixture=(Path(__file__).resolve().parents[2]/"fixtures"/"demo_papers.json"
                     if state["mode"]=="demo" and not args.gold_csv else None)
            result=evaluate(state,fixture_file=fixture,manual_minutes=args.manual_minutes,
                            gold_csv=args.gold_csv)
            path=engine.store.output_dir(args.run_id)/"evaluation.json"
            path.write_text(json.dumps(result,indent=2),encoding="utf-8")
            print(json.dumps(result,indent=2))
        return 0
    except Exception as exc:
        print(f"ERROR ({type(exc).__name__}): {exc}",file=sys.stderr)
        return 1

if __name__=="__main__":
    raise SystemExit(main())
