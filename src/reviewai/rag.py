"""Persistent per-run hybrid retrieval: dense vectors plus token-frequency BM25.

Demo uses deterministic hashing vectors (NOT semantic embeddings); live uses Gemini
embeddings. A small local NumPy index replaces an external vector DB.
"""
from __future__ import annotations
import json
import math
import re
from pathlib import Path
import numpy as np


def chunk_text(text: str, chunk_size: int = 1100, overlap: int = 140) -> list[str]:
    if not text.strip():
        return []
    if not 0 <= overlap < chunk_size:
        raise ValueError("overlap must be smaller than chunk size")
    return [text[start:start + chunk_size] for start in range(0,len(text),chunk_size-overlap)]


def tokens(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", s.lower())


class HybridRAG:
    """Dense cosine similarity + BM25 with source identifiers and excerpt truncation."""
    def __init__(self, folder: Path, provider):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.provider = provider
        self.chunks: list[dict] = []
        self.vectors: np.ndarray | None = None

    def build(self, papers: list[dict]) -> int:
        self.chunks = []
        for paper in papers:
            if not paper.get("full_text"):
                continue
            for i, text in enumerate(chunk_text(paper["full_text"])):
                self.chunks.append({"id":f"{paper['id']}:chunk:{i}","paper_id":paper["id"],
                                    "title":paper["title"],"text":text,"scope":"fulltext"})
        if not self.chunks:
            self.vectors = np.empty((0,0))
            return 0
        self.vectors = self.provider.embed([c["title"] + " " + c["text"] for c in self.chunks])
        if len(self.vectors) != len(self.chunks):
            raise ValueError("RAG vectors/chunks count mismatch")
        (self.folder / "chunks.json").write_text(json.dumps(self.chunks,ensure_ascii=False,indent=2),encoding="utf-8")
        np.save(self.folder / "vectors.npy", self.vectors, allow_pickle=False)
        (self.folder / "index_manifest.json").write_text(json.dumps({
            "mode":self.provider.mode,"model":self.provider.embedding_model,"chunks":len(self.chunks),
            "representation":"Gemini semantic embedding" if self.provider.mode=="live" else "demo lexical hashing (not semantic)"
        }, indent=2),encoding="utf-8")
        return len(self.chunks)

    def load(self):
        self.chunks = json.loads((self.folder / "chunks.json").read_text(encoding="utf-8"))
        self.vectors = np.load(self.folder / "vectors.npy", allow_pickle=False)

    def _bm25(self, query: str) -> np.ndarray:
        docs = [tokens(c["title"] + " " + c["text"]) for c in self.chunks]
        q = list(set(tokens(query)))
        if not docs:
            return np.array([],dtype=float)
        avgdl = sum(map(len,docs)) / len(docs)
        df = {t:sum(t in set(doc) for doc in docs) for t in q}
        scores = []
        for doc in docs:
            from collections import Counter
            counts = Counter(doc)
            score = 0.0
            for t in q:
                tf = counts.get(t,0)
                if not tf:
                    continue
                idf = math.log(1+(len(docs)-df[t]+0.5)/(df[t]+0.5))
                score += idf * (tf * 2.2)/(tf + 1.2*(0.25+0.75*len(doc)/(avgdl or 1)))
            scores.append(score)
        arr = np.array(scores,dtype=float)
        return arr/(arr.max() or 1)

    def search(self, question: str, limit: int = 6, max_excerpt: int = 800) -> list[dict]:
        if self.vectors is None:
            raise RuntimeError("RAG index not built/loaded")
        if not len(self.chunks):
            return []
        query = self.provider.embed([question],query=True)[0]
        norm_v = np.linalg.norm(self.vectors,axis=1)
        cos = (self.vectors @ query) / (norm_v * (np.linalg.norm(query) or 1) + 1e-10)
        dense = (cos + 1) / 2
        sparse = self._bm25(question)
        scores = .65*dense + .35*sparse
        indices = np.argsort(-scores)[:max(1,limit)]
        return [{**self.chunks[int(i)], "text":self.chunks[int(i)]["text"][:max_excerpt],
                 "score":round(float(scores[int(i)]),4)} for i in indices]
