"""Serializable workflow state; uses only JSON-compatible values."""
from typing import Any, TypedDict

class ReviewState(TypedDict, total=False):
    run_id: str
    topic: str
    mode: str
    protocol: dict[str, Any]
    queries: list[str]
    search_events: list[dict[str, Any]]
    papers: list[dict[str, Any]]
    title_screen: list[dict[str, Any]]
    fulltext_screen: list[dict[str, Any]]
    extractions: list[dict[str, Any]]
    rag_hits: list[dict[str, Any]]
    synthesis: dict[str, Any]
    quality_assurance: dict[str, Any]
    prisma: dict[str, Any]
    runtime: str
    elapsed_seconds: float
