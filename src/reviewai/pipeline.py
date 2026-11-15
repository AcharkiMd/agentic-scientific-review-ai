"""Two-phase LangGraph workflow with explicit human approval.

Prepare: coordinator -> search strategy -> retrieval -> dual title screening.
Continue: retrieve PDFs -> dual full-text screening -> extraction -> RAG+synthesis
          -> deterministic critic -> artifacts.

SQLite snapshots are written after each node. Without LangGraph, *demo mode only*
runs an equivalent sequential path for offline verification; live mode refuses fallback.
"""
from __future__ import annotations
import time
from pathlib import Path
from typing import Callable
from .agents import (plan,strategy,screen,extract,synthesize,prisma_counts,critic)
from .config import Settings
from .pdf_ingest import fetch_fulltext
from .provider import DemoProvider,GeminiProvider
from .rag import HybridRAG
from .sources import AcademicSources,fixture_papers
from .storage import Store


class _OfflineSequentialGraph:
    """Explicit test-only demonstration substitute when LangGraph isn't installed."""
    def __init__(self,nodes: list[tuple[str,Callable]]):
        self.nodes = nodes

    def invoke(self,state: dict) -> dict:
        s = dict(state)
        for _,fn in self.nodes:
            s.update(fn(s))
        return s


def _compile(nodes: list[tuple[str,Callable]], allow_offline_fallback: bool):
    try:
        from langgraph.graph import StateGraph, START, END
        from .types import ReviewState
        graph = StateGraph(ReviewState)
        for name,fn in nodes:
            graph.add_node(name,fn)
        graph.add_edge(START,nodes[0][0])
        for (a,_),(b,_) in zip(nodes,nodes[1:]):
            graph.add_edge(a,b)
        graph.add_edge(nodes[-1][0],END)
        return graph.compile(),"langgraph"
    except ImportError:
        if not allow_offline_fallback:
            raise RuntimeError("Live mode requires LangGraph. Run `pip install -e .` first.")
        return _OfflineSequentialGraph(nodes),"offline-sequential-demo-fallback"


class ReviewEngine:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        self.store = Store(self.settings.data_dir)
        self.provider = None

    def _provider(self, mode: str):
        return DemoProvider() if mode=="demo" else GeminiProvider(
            self.settings.gemini_key,self.settings.gemini_model,self.settings.embedding_model)

    def _wrap(self, name: str, fn: Callable):
        def node(state):
            start=time.monotonic()
            try:
                result = fn(state)
                output = {**state,**result}
                self.store.save(output)
                self.store.event(state["run_id"],name,{"result_keys":list(result.keys()),
                                  "duration_seconds":round(time.monotonic()-start,3)})
                return result
            except Exception as exc:
                self.store.event(state["run_id"],name,{"error":str(exc)[:500]},"error")
                raise
        return (name,node)

    def prepare(self, topic: str, mode: str = "demo", max_papers: int | None = None) -> dict:
        if len(topic.strip()) < 12:
            raise ValueError("Please enter a meaningful research question (at least 12 characters)")
        if mode == "demo" and "lakehouse" not in topic.lower():
            raise ValueError("Synthetic fixture only supports lakehouse topics; choose live mode for other research questions")
        max_papers = max_papers or self.settings.max_papers
        if not 1 <= max_papers <= 100:
            raise ValueError("max_papers must be between 1 and 100")
        self.provider = self._provider(mode)  # Verify Gemini credentials before creating a run.
        state = self.store.create(topic.strip(),mode)
        initial=time.monotonic()
        try:
            nodes = [
                self._wrap("coordinator_protocol",lambda s:{"protocol":plan(self.provider,s["topic"],max_papers)}),
                self._wrap("search_strategy",lambda s:{"queries":strategy(self.provider,s["protocol"])}),
                self._wrap("retrieval",lambda s:self._retrieve(s)),
                self._wrap("dual_title_screening",lambda s:{"title_screen":screen(
                    self.provider,s["papers"],s["protocol"],"title")}),
            ]
            graph,runtime = _compile(nodes,allow_offline_fallback=(mode=="demo"))
            state["runtime"] = runtime
            state = graph.invoke(state)
            state["elapsed_seconds"] = time.monotonic()-initial
            self.store.save(state,"awaiting_approval")
            return state
        except Exception:
            self.store.save(self.store.get(state["run_id"])["state"],"failed_prepare")
            raise

    def _retrieve(self,state: dict) -> dict:
        if state["mode"]=="demo":
            root = Path(__file__).resolve().parents[2]
            papers,events = fixture_papers(root)
        else:
            api = AcademicSources(timeout=self.settings.timeout,
                                  openalex_key=self.settings.openalex_key,
                                  openalex_email=self.settings.openalex_email)
            papers,events = api.search(state["queries"],
                                       max_papers=state["protocol"]["max_papers"],
                                       year_start=state["protocol"].get("publication_year_start"))
        if not papers:
            raise RuntimeError("Academic retrieval returned zero papers; adjust the search strategy")
        self.store.event(state["run_id"],"search_provenance",{"events":events})
        return {"papers":papers,"search_events":events}

    def continue_review(self, run_id: str, approve: bool = False) -> dict:
        record = self.store.get(run_id)
        if record["status"] != "awaiting_approval":
            raise ValueError(f"Run {run_id} is not awaiting approval ({record['status']})")
        if approve and not record["approved"]:
            self.store.approve(run_id)
            record=self.store.get(run_id)
        if not record["approved"]:
            raise PermissionError("A human must approve the protocol and screening decisions first")
        state=record["state"]
        self.provider=self._provider(state["mode"])
        overrides=self.store.overrides(run_id)
        decisions=[]
        for d in state["title_screen"]:
            r=dict(d)
            if r["paper_id"] in overrides:
                human=overrides[r["paper_id"]]
                r["decision"]=human["decision"]
                r["rationale"]="HUMAN OVERRIDE: "+human["reason"]
                r["human_override"]=True
            decisions.append(r)
        unresolved=[d["paper_id"] for d in decisions if d["decision"]=="uncertain"]
        if unresolved:
            raise ValueError("Resolve uncertain title-screening cases via overrides: "+", ".join(unresolved))
        state["title_screen"] = decisions
        state["elapsed_seconds"] = float(state.get("elapsed_seconds",0))
        initial=time.monotonic()
        try:
            nodes=[
                self._wrap("fulltext_retrieval",lambda s:self._fulltexts(s)),
                self._wrap("dual_fulltext_screening",lambda s:self._full_screen(s)),
                self._wrap("evidence_extraction_appraisal",lambda s:self._extractions(s)),
                self._wrap("hybrid_rag_synthesis",lambda s:self._synthesis(s)),
                self._wrap("prisma_and_critic",lambda s:self._qa(s)),
            ]
            graph,runtime = _compile(nodes,allow_offline_fallback=(state["mode"]=="demo"))
            state["runtime"] = runtime
            self.store.save(state,"running")
            state=graph.invoke(state)
            state["elapsed_seconds"] += time.monotonic()-initial
            self.store.save(state,"completed")
            self.store.event(run_id,"completion",{"elapsed_seconds":round(state["elapsed_seconds"],2)})
            from .exports import export_run
            export_run(self.store,run_id)
            return state
        except Exception:
            self.store.save(self.store.get(run_id)["state"],"failed_completion")
            raise

    def _fulltexts(self,state:dict)->dict:
        kept={d["paper_id"] for d in state["title_screen"] if d["decision"]=="include"}
        out=[]
        for paper in state["papers"]:
            p=dict(paper)
            if p["id"] in kept and state["mode"]=="live":
                p=fetch_fulltext(p,timeout=self.settings.timeout)
            out.append(p)
        return {"papers":out}

    def _full_screen(self,state:dict)->dict:
        kept={d["paper_id"] for d in state["title_screen"] if d["decision"]=="include"}
        candidates=[p for p in state["papers"] if p["id"] in kept]
        return {"fulltext_screen":screen(self.provider,candidates,state["protocol"],"fulltext")}

    def _extractions(self,state:dict)->dict:
        included={d["paper_id"] for d in state["fulltext_screen"] if d["decision"]=="include"}
        extracted=[extract(self.provider,p) for p in state["papers"] if p["id"] in included]
        return {"extractions":extracted}

    def _synthesis(self,state:dict)->dict:
        included={e["paper_id"] for e in state["extractions"]}
        papers=[p for p in state["papers"] if p["id"] in included]
        rag=HybridRAG(self.store.output_dir(state["run_id"])/"rag",self.provider)
        count=rag.build(papers)
        hits=rag.search(state["protocol"]["research_question"],limit=6) if count else []
        return {"rag_hits":hits,"synthesis":synthesize(self.provider,state["protocol"],
                                                         state["extractions"],hits)}

    def _qa(self,state:dict)->dict:
        counts=prisma_counts(state["papers"],state["search_events"],
                             state["title_screen"],state["fulltext_screen"])
        output={**state,"prisma":counts}
        return {"prisma":counts,"quality_assurance":critic(output)}
