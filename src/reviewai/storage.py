"""SQLite run snapshots, audit events, human decisions, and exported artifacts.

No API keys are persisted; timestamps are UTC. Every state change increments a version.
"""
from __future__ import annotations
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, data_dir: Path | str):
        self.root = Path(data_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = self.root / "reviews.sqlite3"
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, topic TEXT NOT NULL, mode TEXT NOT NULL,
                    status TEXT NOT NULL, state_json TEXT NOT NULL,
                    approved INTEGER NOT NULL DEFAULT 0, version INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
                    stage TEXT NOT NULL, level TEXT NOT NULL, payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS ix_events_run ON events(run_id,event_id);
                CREATE TABLE IF NOT EXISTS overrides (
                    run_id TEXT NOT NULL, paper_id TEXT NOT NULL,
                    decision TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL,
                    PRIMARY KEY (run_id,paper_id));
            """)

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(self.db, timeout=30)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=30000")
            with conn:
                yield conn
        finally:
            conn.close()

    def create(self, topic: str, mode: str) -> dict[str, Any]:
        if mode not in {"demo", "live"}:
            raise ValueError("mode must be 'demo' or 'live'")
        run_id = uuid.uuid4().hex[:12]
        state = {"run_id": run_id, "topic": topic, "mode": mode}
        with self.connection() as db:
            db.execute("INSERT INTO runs (id,topic,mode,status,state_json,created_at,updated_at) "
                       "VALUES (?,?,?,?,?,?,?)",
                       (run_id, topic, mode, "created", json.dumps(state), now(), now()))
        self.event(run_id, "create", {"topic": topic, "mode": mode})
        return state

    def get(self, run_id: str) -> dict[str, Any]:
        with self.connection() as db:
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(f"Review run not found: {run_id}")
        data = dict(row)
        data["state"] = json.loads(data.pop("state_json"))
        data["approved"] = bool(data["approved"])
        return data

    def list_runs(self) -> list[dict[str, Any]]:
        with self.connection() as db:
            return [dict(r) for r in db.execute(
                "SELECT id,topic,mode,status,approved,version,created_at,updated_at "
                "FROM runs ORDER BY created_at DESC,id DESC LIMIT 100").fetchall()]

    def save(self, state: dict, status: str | None = None) -> None:
        run_id = state["run_id"]
        with self.connection() as db:
            row = db.execute("SELECT status FROM runs WHERE id=?", (run_id,)).fetchone()
            if not row:
                raise KeyError(run_id)
            db.execute("UPDATE runs SET state_json=?,status=?,version=version+1,updated_at=? WHERE id=?",
                       (json.dumps(state, ensure_ascii=False), status or row[0], now(), run_id))

    def approve(self, run_id: str, protocol: dict | None = None) -> None:
        row = self.get(run_id)
        if row["status"] != "awaiting_approval":
            raise ValueError("Review is not awaiting approval")
        state = row["state"]
        if protocol is not None:
            from .agents import validate_protocol
            validate_protocol(protocol)
            # Changing an approved protocol would invalidate already generated searches and screening.
            # Require the user to start a new run for a materially different protocol.
            if protocol != state["protocol"]:
                raise ValueError("Changing the protocol after screening is not allowed; start a new run")
        with self.connection() as db:
            db.execute("UPDATE runs SET approved=1,updated_at=? WHERE id=?", (now(), run_id))
        self.event(run_id, "human_approval", {"protocol_version": state["protocol"].get("version", "1.0")})

    def override(self, run_id: str, paper_id: str, decision: str, reason: str) -> None:
        if decision not in {"include", "exclude", "uncertain"}:
            raise ValueError("Decision must be include/exclude/uncertain")
        if not reason.strip():
            raise ValueError("Human override requires an explanation")
        row = self.get(run_id)
        if row["status"] != "awaiting_approval":
            raise ValueError("Screening overrides are available only before continuation")
        if paper_id not in {p["id"] for p in row["state"].get("papers", [])}:
            raise ValueError("Unknown paper ID")
        with self.connection() as db:
            db.execute("INSERT OR REPLACE INTO overrides(run_id,paper_id,decision,reason,created_at) "
                       "VALUES(?,?,?,?,?)", (run_id,paper_id,decision,reason,now()))
        self.event(run_id, "human_screening_override", {"paper_id": paper_id, "decision": decision, "reason": reason})

    def overrides(self, run_id: str) -> dict[str, dict]:
        with self.connection() as db:
            rows = db.execute("SELECT * FROM overrides WHERE run_id=?", (run_id,)).fetchall()
        return {r["paper_id"]: dict(r) for r in rows}

    def event(self, run_id: str, stage: str, payload: dict, level: str = "info") -> None:
        with self.connection() as db:
            db.execute("INSERT INTO events(run_id,stage,level,payload_json,created_at) VALUES(?,?,?,?,?)",
                       (run_id,stage,level,json.dumps(payload,ensure_ascii=False,default=str),now()))

    def events(self, run_id: str) -> list[dict]:
        with self.connection() as db:
            rows = db.execute("SELECT * FROM events WHERE run_id=? ORDER BY event_id", (run_id,)).fetchall()
        return [{**dict(r),"payload":json.loads(r["payload_json"])} for r in rows]

    def output_dir(self, run_id: str) -> Path:
        folder = self.root / "runs" / run_id
        folder.mkdir(parents=True,exist_ok=True)
        return folder
