from __future__ import annotations

import builtins
import json
import os
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Protocol, runtime_checkable

from core.scan_state import ScanRunState, is_terminal, transition


@dataclass(slots=True)
class PersistedScanEvent:
    timestamp: str
    stage: str
    message: str
    progress: int
    level: str = "info"
    event_id: int = 0
    type: str = "phase_started"
    phase: str | None = None
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PersistedScanJob:
    id: str
    target: str
    profile: str
    authorised: bool
    created_by: str = "anonymous"
    status: str = "queued"
    progress: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None
    events: list[PersistedScanEvent] = field(default_factory=list)
    outputs: dict[str, str] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)
    transitions: list[dict[str, Any]] = field(default_factory=list)

    def apply_transition(self, target: str, actor: str = "system", reason: str = "") -> str:
        """Move the run to ``target``, recording the move as a first-class row.

        Raises :class:`core.scan_state.InvalidScanTransition` when the move is
        illegal, so a bad status assignment fails loudly instead of corrupting
        the record.
        """
        previous = self.status
        state = transition(previous, target)
        self.status = state.value
        self.transitions.append(
            {
                "from_state": str(previous),
                "to_state": state.value,
                "at": datetime.now(timezone.utc).isoformat(),
                "actor": actor,
                "reason": reason,
            }
        )
        return state.value

    def add_event(
        self,
        stage: str,
        message: str,
        progress: int,
        level: str = "info",
        data: dict[str, Any] | None = None,
    ) -> None:
        self.progress = progress
        etype = {
            "queued": "scan_queued",
            "initialising": "scan_started",
            "target_validation": "target_validated",
            "completed": "scan_completed",
            "failed": "scan_failed",
            "cancelled": "scan_failed",
            "timed_out": "scan_failed",
            "finding": "finding_created",
            "evidence": "evidence_saved",
            "report": "report_written",
        }.get(
            stage,
            stage
            if stage
            in {
                "scan_queued",
                "scan_started",
                "target_validated",
                "phase_started",
                "check_started",
                "check_completed",
                "finding_created",
                "evidence_saved",
                "report_written",
                "scan_completed",
                "scan_failed",
                "heartbeat",
                "state_changed",
            }
            else "phase_started",
        )
        self.events.append(
            PersistedScanEvent(
                datetime.now(timezone.utc).isoformat(),
                stage,
                message,
                progress,
                level,
                event_id=len(self.events) + 1,
                type=etype,
                phase=stage,
                data=dict(data or {}),
            )
        )

    def to_dict(self, include_events: bool = True) -> dict[str, Any]:
        data = asdict(self)
        if not include_events:
            data.pop("events", None)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PersistedScanJob:
        events = [PersistedScanEvent(**event) for event in data.get("events", [])]
        data = {**data, "events": events, "transitions": list(data.get("transitions") or [])}
        return cls(**data)


FINDING_STATE_FIELDS: tuple[str, ...] = (
    "status",
    "severity",
    "triage_state",
    "owner",
    "remediation_note",
    "due_date",
    "false_positive_reason",
    "accepted_risk_reason",
)


def _merge_finding_state(previous: dict[str, Any], patch: dict[str, Any], actor: str) -> dict[str, Any]:
    """Apply a triage patch onto the previous finding state.

    Only the whitelisted remediation fields are writable; everything else in the
    request body is ignored so a client cannot inject arbitrary keys.
    """
    defaults: dict[str, Any] = {field: None for field in FINDING_STATE_FIELDS}
    defaults["status"] = "open"
    return {
        **defaults,
        **{key: value for key, value in previous.items() if key in defaults},
        **{key: value for key, value in patch.items() if key in defaults},
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": actor,
    }


@runtime_checkable
class JobStore(Protocol):
    """Storage interface for scan job persistence."""

    def create(
        self, target: str, profile: str, authorised: bool, created_by: str = "anonymous"
    ) -> PersistedScanJob: ...

    def get(self, job_id: str) -> PersistedScanJob | None: ...

    def list(self) -> list[PersistedScanJob]: ...

    def update(self, job_id: str, fn) -> PersistedScanJob | None: ...

    def list_events_after(self, job_id: str, after_id: int = 0) -> builtins.list[PersistedScanEvent]: ...

    def list_findings(self, scan_id: str) -> builtins.list[dict[str, Any]]: ...

    def update_finding(
        self, scan_id: str, finding_id: str, patch: dict[str, Any], actor: str
    ) -> dict[str, Any] | None: ...

    def finding_history(self, scan_id: str, finding_id: str) -> builtins.list[dict[str, Any]]: ...

    def reconcile_interrupted(self, reason: str) -> builtins.list[str]: ...


class PersistentJobStore:
    """JSON-file scan job store, used when VULNORAIQ_JOB_STORE_BACKEND=json."""

    def __init__(self, path: str | Path = "reports/output/webui/jobs.json") -> None:
        self.path = Path(path)
        self._lock = RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def create(self, target: str, profile: str, authorised: bool, created_by: str = "anonymous") -> PersistedScanJob:
        job = PersistedScanJob(uuid.uuid4().hex[:12], target, profile, authorised, created_by=created_by)
        job.add_event("queued", "Scan queued and waiting for worker thread.", 0)
        with self._lock:
            jobs = self._load_all()
            jobs[job.id] = job
            self._save_all(jobs)
        return job

    def get(self, job_id: str) -> PersistedScanJob | None:
        with self._lock:
            return self._load_all().get(job_id)

    def list(self) -> list[PersistedScanJob]:
        with self._lock:
            return sorted(self._load_all().values(), key=lambda item: item.created_at, reverse=True)

    def update(self, job_id: str, fn) -> PersistedScanJob | None:
        with self._lock:
            jobs = self._load_all()
            job = jobs.get(job_id)
            if not job:
                return None
            fn(job)
            jobs[job_id] = job
            self._save_all(jobs)
            return job

    def list_events_after(self, job_id: str, after_id: int = 0) -> builtins.list[PersistedScanEvent]:
        job = self.get(job_id)
        if not job:
            return []
        return [event for event in job.events if event.event_id > after_id]

    def list_findings(self, scan_id: str) -> builtins.list[dict[str, Any]]:
        job = self.get(scan_id)
        return list(job.summary.get("findings") or []) if job else []

    def update_finding(self, scan_id: str, finding_id: str, patch: dict[str, Any], actor: str) -> dict[str, Any] | None:
        with self._lock:
            jobs = self._load_all()
            job = jobs.get(scan_id)
            if not job:
                return None
            findings = list(job.summary.get("findings") or [])
            index = next(
                (
                    i
                    for i, finding in enumerate(findings)
                    if str(finding.get("id") or finding.get("owasp_id")) == finding_id
                ),
                None,
            )
            if index is None:
                return None
            previous = dict(findings[index].get("remediation_state") or {"status": "open"})
            new_state = _merge_finding_state(previous, patch, actor)
            findings[index] = {
                **findings[index],
                "id": finding_id,
                "remediation_state": new_state,
                "status": new_state["status"],
            }
            job.summary["findings"] = findings
            history = job.summary.setdefault("finding_history", [])
            history.append(
                {
                    "scan_id": scan_id,
                    "finding_id": finding_id,
                    "previous_state": previous,
                    "new_state": new_state,
                    "actor": actor,
                    "timestamp": new_state["updated_at"],
                    "note": str(patch.get("note") or patch.get("remediation_note") or "")[:500],
                }
            )
            jobs[scan_id] = job
            self._save_all(jobs)
            return new_state

    def finding_history(self, scan_id: str, finding_id: str) -> builtins.list[dict[str, Any]]:
        job = self.get(scan_id)
        if not job:
            return []
        return [
            entry
            for entry in (job.summary.get("finding_history") or [])
            if entry.get("finding_id") == finding_id
        ]

    def reconcile_interrupted(self, reason: str) -> builtins.list[str]:
        """Fail every job left mid-run by a process that no longer exists.

        A non-terminal row at boot belongs to a thread that died with the last
        process, so leaving it ``running`` strands it forever.
        """
        recovered: builtins.list[str] = []
        with self._lock:
            jobs = self._load_all()
            for job_id, job in jobs.items():
                if is_terminal(job.status):
                    continue
                job.apply_transition(ScanRunState.FAILED.value, actor="system", reason=reason)
                job.error = reason
                job.completed_at = datetime.now(timezone.utc).isoformat()
                job.add_event("failed", reason, 100, level="error")
                recovered.append(job_id)
            if recovered:
                self._save_all(jobs)
        return recovered

    def _load_all(self) -> dict[str, PersistedScanJob]:
        if not self.path.exists():
            return {}
        raw = json.loads(self.path.read_text(encoding="utf-8") or "{}")
        return {job_id: PersistedScanJob.from_dict(value) for job_id, value in raw.items()}

    def _save_all(self, jobs: dict[str, PersistedScanJob]) -> None:
        self.path.write_text(
            json.dumps({job_id: job.to_dict() for job_id, job in jobs.items()}, indent=2, sort_keys=True),
            encoding="utf-8",
        )


class SqliteJobStore:
    """SQLite-backed scan job store for production use."""

    SCHEMA_VERSION = 3

    def __init__(self, path: str | Path = "reports/output/webui/jobs.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript("PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON; PRAGMA busy_timeout=5000;")
        self._lock = RLock()
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS _schema_version (
                version INTEGER PRIMARY KEY
            );
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                target TEXT NOT NULL,
                profile TEXT NOT NULL,
                authorised INTEGER NOT NULL DEFAULT 0,
                created_by TEXT NOT NULL DEFAULT 'anonymous',
                status TEXT NOT NULL DEFAULT 'queued',
                progress INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                error TEXT,
                outputs TEXT NOT NULL DEFAULT '{}',
                summary TEXT NOT NULL DEFAULT '{}'
            );
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                timestamp TEXT NOT NULL,
                stage TEXT NOT NULL,
                message TEXT NOT NULL,
                progress INTEGER NOT NULL DEFAULT 0,
                level TEXT NOT NULL DEFAULT 'info',
                type TEXT NOT NULL DEFAULT 'phase_started',
                phase TEXT,
                data TEXT NOT NULL DEFAULT '{}'
            );
            CREATE TABLE IF NOT EXISTS finding_states (
                scan_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                finding_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                severity TEXT,
                triage_state TEXT,
                owner TEXT,
                remediation_note TEXT,
                due_date TEXT,
                false_positive_reason TEXT,
                accepted_risk_reason TEXT,
                updated_at TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                PRIMARY KEY (scan_id, finding_id)
            );
            CREATE TABLE IF NOT EXISTS finding_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id TEXT NOT NULL,
                finding_id TEXT NOT NULL,
                previous_state TEXT NOT NULL DEFAULT '{}',
                new_state TEXT NOT NULL DEFAULT '{}',
                actor TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                note TEXT
            );
            CREATE TABLE IF NOT EXISTS scan_transitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                from_state TEXT NOT NULL,
                to_state TEXT NOT NULL,
                at TEXT NOT NULL,
                actor TEXT NOT NULL DEFAULT 'system',
                reason TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_scan_transitions_job_id ON scan_transitions(job_id);
            CREATE INDEX IF NOT EXISTS idx_events_job_id ON events(job_id);
            CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at);
        """)
        for stmt in (
            "ALTER TABLE events ADD COLUMN type TEXT NOT NULL DEFAULT 'phase_started'",
            "ALTER TABLE events ADD COLUMN phase TEXT",
            "ALTER TABLE events ADD COLUMN data TEXT NOT NULL DEFAULT '{}'",
        ):
            try:
                self._conn.execute(stmt)
            except sqlite3.OperationalError:
                pass
        self._conn.commit()
        self._ensure_schema_version()

    def _ensure_schema_version(self) -> None:
        row = self._conn.execute("SELECT MAX(version) FROM _schema_version").fetchone()
        current_version = row[0] if row and row[0] else 0
        if current_version < self.SCHEMA_VERSION:
            self._conn.execute("INSERT OR REPLACE INTO _schema_version (version) VALUES (?)", (self.SCHEMA_VERSION,))
            self._conn.commit()

    def create(self, target: str, profile: str, authorised: bool, created_by: str = "anonymous") -> PersistedScanJob:
        job = PersistedScanJob(uuid.uuid4().hex[:12], target, profile, authorised, created_by=created_by)
        job.add_event("queued", "Scan queued and waiting for worker thread.", 0)
        with self._lock:
            self._insert_job(job)
        return job

    def get(self, job_id: str) -> PersistedScanJob | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if not row:
                return None
            return self._row_to_job(row)

    def list(self) -> list[PersistedScanJob]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
            return [self._row_to_job(row) for row in rows]

    def update(self, job_id: str, fn) -> PersistedScanJob | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if not row:
                return None
            job = self._row_to_job(row)
            fn(job)
            self._update_job(job)
            return job

    def _insert_job(self, job: PersistedScanJob) -> None:
        self._conn.execute(
            """INSERT INTO jobs (id, target, profile, authorised, created_by, status, progress,
               created_at, started_at, completed_at, error, outputs, summary)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                job.id,
                job.target,
                job.profile,
                int(job.authorised),
                job.created_by,
                job.status,
                job.progress,
                job.created_at,
                job.started_at,
                job.completed_at,
                job.error,
                json.dumps(job.outputs, sort_keys=True),
                json.dumps(job.summary, default=str, sort_keys=True),
            ),
        )
        for ev in job.events:
            self._insert_event(job.id, ev)
        for item in job.transitions:
            self._insert_transition(job.id, item)
        self._conn.commit()

    def _update_job(self, job: PersistedScanJob) -> None:
        self._conn.execute(
            """UPDATE jobs SET status=?, progress=?, started_at=?, completed_at=?, error=?,
               outputs=?, summary=? WHERE id=?""",
            (
                job.status,
                job.progress,
                job.started_at,
                job.completed_at,
                job.error,
                json.dumps(job.outputs, sort_keys=True),
                json.dumps(job.summary, default=str, sort_keys=True),
                job.id,
            ),
        )
        stored = self._conn.execute(
            "SELECT COUNT(*) FROM events WHERE job_id = ?", (job.id,)
        ).fetchone()[0]
        for ev in job.events[stored:]:
            self._insert_event(job.id, ev)
        stored_transitions = self._conn.execute(
            "SELECT COUNT(*) FROM scan_transitions WHERE job_id = ?", (job.id,)
        ).fetchone()[0]
        for item in job.transitions[stored_transitions:]:
            self._insert_transition(job.id, item)
        self._conn.commit()

    def _insert_event(self, job_id: str, ev: PersistedScanEvent) -> None:
        self._conn.execute(
            "INSERT INTO events (job_id, timestamp, stage, message, progress, level, type, phase, data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                job_id,
                ev.timestamp,
                ev.stage,
                ev.message,
                ev.progress,
                ev.level,
                ev.type,
                ev.phase,
                json.dumps(ev.data, sort_keys=True),
            ),
        )

    def _insert_transition(self, job_id: str, item: dict[str, Any]) -> None:
        self._conn.execute(
            "INSERT INTO scan_transitions (job_id, from_state, to_state, at, actor, reason) VALUES (?, ?, ?, ?, ?, ?)",
            (
                job_id,
                str(item.get("from_state", "")),
                str(item.get("to_state", "")),
                str(item.get("at", "")),
                str(item.get("actor", "system")),
                str(item.get("reason", "")),
            ),
        )

    def _row_to_job(self, row: sqlite3.Row) -> PersistedScanJob:
        events = self._conn.execute(
            "SELECT id as event_id, timestamp, stage, message, progress, level, type, phase, data FROM events WHERE job_id = ? ORDER BY id",
            (row["id"],),
        ).fetchall()
        return PersistedScanJob(
            id=row["id"],
            target=row["target"],
            profile=row["profile"],
            authorised=bool(row["authorised"]),
            created_by=row["created_by"],
            status=row["status"],
            progress=row["progress"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            error=row["error"],
            events=[
                PersistedScanEvent(**{**dict(ev), "data": json.loads(dict(ev).get("data") or "{}")}) for ev in events
            ],
            outputs=json.loads(row["outputs"] or "{}"),
            summary=json.loads(row["summary"] or "{}"),
            transitions=[
                dict(item)
                for item in self._conn.execute(
                    "SELECT from_state, to_state, at, actor, reason FROM scan_transitions WHERE job_id = ? ORDER BY id",
                    (row["id"],),
                ).fetchall()
            ],
        )

    def list_events_after(self, job_id: str, after_id: int = 0) -> builtins.list[PersistedScanEvent]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id as event_id, timestamp, stage, message, progress, level, type, phase, data FROM events WHERE job_id = ? AND id > ? ORDER BY id",
                (job_id, after_id),
            ).fetchall()
            return [
                PersistedScanEvent(**{**dict(row), "data": json.loads(dict(row).get("data") or "{}")}) for row in rows
            ]

    def list_findings(self, scan_id: str) -> builtins.list[dict[str, Any]]:
        job = self.get(scan_id)
        if not job:
            return []
        findings = list(job.summary.get("findings") or [])
        states = {
            r["finding_id"]: dict(r)
            for r in self._conn.execute("SELECT * FROM finding_states WHERE scan_id=?", (scan_id,)).fetchall()
        }
        for idx, finding in enumerate(findings):
            fid = str(finding.get("id") or finding.get("owasp_id") or f"finding-{idx + 1}")
            finding.setdefault("id", fid)
            state = states.get(fid)
            if state:
                finding["remediation_state"] = state
                finding["status"] = state["status"]
        return findings

    def update_finding(self, scan_id: str, finding_id: str, patch: dict[str, Any], actor: str) -> dict[str, Any] | None:
        if not any(str(f.get("id") or f.get("owasp_id")) == finding_id for f in self.list_findings(scan_id)):
            return None
        now = datetime.now(timezone.utc).isoformat()
        prev = self._conn.execute(
            "SELECT * FROM finding_states WHERE scan_id=? AND finding_id=?", (scan_id, finding_id)
        ).fetchone()
        previous = dict(prev) if prev else {"status": "open"}
        new = {
            **_merge_finding_state(previous, patch, actor),
            "scan_id": scan_id,
            "finding_id": finding_id,
            "updated_at": now,
        }
        self._conn.execute(
            """INSERT OR REPLACE INTO finding_states (scan_id,finding_id,status,severity,triage_state,owner,remediation_note,due_date,false_positive_reason,accepted_risk_reason,updated_at,updated_by) VALUES (:scan_id,:finding_id,:status,:severity,:triage_state,:owner,:remediation_note,:due_date,:false_positive_reason,:accepted_risk_reason,:updated_at,:updated_by)""",
            new,
        )
        self._conn.execute(
            "INSERT INTO finding_history (scan_id,finding_id,previous_state,new_state,actor,timestamp,note) VALUES (?,?,?,?,?,?,?)",
            (
                scan_id,
                finding_id,
                json.dumps(previous, sort_keys=True, default=str),
                json.dumps(new, sort_keys=True, default=str),
                actor,
                now,
                str(patch.get("note") or patch.get("remediation_note") or "")[:500],
            ),
        )
        self._conn.commit()
        return new

    def finding_history(self, scan_id: str, finding_id: str) -> builtins.list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM finding_history WHERE scan_id=? AND finding_id=? ORDER BY id", (scan_id, finding_id)
        ).fetchall()
        return [dict(r) for r in rows]

    def reconcile_interrupted(self, reason: str) -> builtins.list[str]:
        """Fail every job left mid-run by a process that no longer exists."""
        recovered: builtins.list[str] = []
        with self._lock:
            rows = self._conn.execute("SELECT id, status FROM jobs").fetchall()
            stranded = [row["id"] for row in rows if not is_terminal(row["status"])]
            for job_id in stranded:
                job = self.get(job_id)
                if job is None:
                    continue
                job.apply_transition(ScanRunState.FAILED.value, actor="system", reason=reason)
                job.error = reason
                job.completed_at = datetime.now(timezone.utc).isoformat()
                job.add_event("failed", reason, 100, level="error")
                self._update_job(job)
                recovered.append(job_id)
        return recovered


def create_job_store() -> JobStore:
    """Factory: returns SqliteJobStore or PersistentJobStore based on VULNORAIQ_JOB_STORE env var."""
    backend = os.getenv("VULNORAIQ_JOB_STORE_BACKEND", "sqlite").strip().lower()
    path = os.getenv("VULNORAIQ_JOB_STORE_PATH", "")
    if backend == "json":
        return PersistentJobStore(path or "reports/output/webui/jobs.json")
    return SqliteJobStore(path or "reports/output/webui/jobs.db")
