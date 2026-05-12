"""Skeleton for Phase 6: agent/artifact_registry.py — typed artifacts with lineage.

SQLite-backed. One table, one DB file at ~/.rasputin/artifacts/registry.db.
Content-addressed dedup by sha256.
"""
from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import secrets
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Optional


SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Artifact:
    id: str
    path: str
    kind: str                       # 'document'|'image'|'audio'|'video'|'code'|'data'|'log'
    media_type: str
    content_hash: str
    size_bytes: int
    produced_by: str                # "<tool_name>/<step_id>"
    derived_from: tuple[str, ...]
    goal_id: str
    sub_agent_id: Optional[str]
    created_at: str
    metadata: dict


class RegistryError(Exception): ...
class ArtifactNotFound(RegistryError): ...
class IncompatibleSchema(RegistryError): ...


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);
INSERT INTO schema_version (version) SELECT ? WHERE NOT EXISTS (SELECT 1 FROM schema_version);

CREATE TABLE IF NOT EXISTS artifact (
    id TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    kind TEXT NOT NULL,
    media_type TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    produced_by TEXT NOT NULL,
    derived_from TEXT NOT NULL,    -- JSON array of artifact ids
    goal_id TEXT NOT NULL,
    sub_agent_id TEXT,
    created_at TEXT NOT NULL,
    metadata TEXT NOT NULL          -- JSON object
);

CREATE INDEX IF NOT EXISTS idx_artifact_goal ON artifact (goal_id);
CREATE INDEX IF NOT EXISTS idx_artifact_hash ON artifact (content_hash);
CREATE INDEX IF NOT EXISTS idx_artifact_kind ON artifact (kind);
"""


def _ulid() -> str:
    ts = int(time.time() * 1000)
    rand = secrets.token_hex(8)
    return f"{ts:013d}-{rand}"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _infer_kind(media_type: str, suffix: str) -> str:
    if media_type.startswith("image/"):
        return "image"
    if media_type.startswith("audio/"):
        return "audio"
    if media_type.startswith("video/"):
        return "video"
    if suffix in (".py", ".js", ".ts", ".sh", ".rs", ".go", ".c", ".cpp", ".java"):
        return "code"
    if suffix in (".csv", ".json", ".tsv", ".parquet", ".xlsx"):
        return "data"
    if suffix in (".log",):
        return "log"
    return "document"


def _sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


class ArtifactRegistry:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        with self._lock, self._conn:
            for stmt in _SCHEMA_SQL.strip().split(";"):
                s = stmt.strip()
                if not s:
                    continue
                if s.startswith("INSERT INTO schema_version"):
                    self._conn.execute(s, (SCHEMA_VERSION,))
                else:
                    self._conn.execute(s)
            row = self._conn.execute("SELECT version FROM schema_version").fetchone()
            if row and row[0] != SCHEMA_VERSION:
                raise IncompatibleSchema(
                    f"DB schema {row[0]} != module {SCHEMA_VERSION}"
                )

    def add(
        self,
        path: Path,
        kind: str | None = None,
        produced_by: str = "unknown",
        goal_id: str = "ad-hoc",
        sub_agent_id: str | None = None,
        derived_from: list[str] | None = None,
        metadata: dict | None = None,
    ) -> Artifact:
        path = Path(path).resolve()
        if not path.exists():
            raise RegistryError(f"file does not exist: {path}")

        content_hash = _sha256_of(path)
        size_bytes = path.stat().st_size
        media_type, _ = mimetypes.guess_type(str(path))
        media_type = media_type or "application/octet-stream"
        kind = kind or _infer_kind(media_type, path.suffix.lower())

        # dedup: existing entry with same hash + same path → reuse
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT id, derived_from, metadata, created_at FROM artifact "
                "WHERE content_hash = ? AND path = ?",
                (content_hash, str(path)),
            ).fetchone()
            if row:
                return self._row_to_artifact(self._fetch_by_id(row[0]))

            artifact_id = _ulid()
            df_json = json.dumps(derived_from or [])
            md_json = json.dumps(metadata or {})
            self._conn.execute(
                "INSERT INTO artifact "
                "(id, path, kind, media_type, content_hash, size_bytes, produced_by, "
                " derived_from, goal_id, sub_agent_id, created_at, metadata) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    artifact_id, str(path), kind, media_type, content_hash, size_bytes,
                    produced_by, df_json, goal_id, sub_agent_id, _utcnow_iso(), md_json,
                ),
            )
            return Artifact(
                id=artifact_id,
                path=str(path),
                kind=kind,
                media_type=media_type,
                content_hash=content_hash,
                size_bytes=size_bytes,
                produced_by=produced_by,
                derived_from=tuple(derived_from or []),
                goal_id=goal_id,
                sub_agent_id=sub_agent_id,
                created_at=_utcnow_iso(),
                metadata=metadata or {},
            )

    def get(self, artifact_id: str) -> Artifact:
        row = self._fetch_by_id(artifact_id)
        if row is None:
            raise ArtifactNotFound(artifact_id)
        return self._row_to_artifact(row)

    def list(
        self,
        goal_id: str | None = None,
        kind: str | None = None,
        sub_agent_id: str | None = None,
    ) -> list[Artifact]:
        sql = "SELECT * FROM artifact WHERE 1=1"
        params: list = []
        if goal_id is not None:
            sql += " AND goal_id = ?"
            params.append(goal_id)
        if kind is not None:
            sql += " AND kind = ?"
            params.append(kind)
        if sub_agent_id is not None:
            sql += " AND sub_agent_id = ?"
            params.append(sub_agent_id)
        sql += " ORDER BY created_at"
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_artifact(r) for r in rows]

    def find_by_hash(self, content_hash: str) -> list[Artifact]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM artifact WHERE content_hash = ?", (content_hash,)
            ).fetchall()
        return [self._row_to_artifact(r) for r in rows]

    def link_lineage(self, artifact_id: str, derived_from: list[str]) -> None:
        with self._lock, self._conn:
            for d in derived_from:
                if self._fetch_by_id(d) is None:
                    raise ArtifactNotFound(f"derived_from missing: {d}")
            existing = self._fetch_by_id(artifact_id)
            if existing is None:
                raise ArtifactNotFound(artifact_id)
            merged = sorted(set(json.loads(existing[7])) | set(derived_from))
            self._conn.execute(
                "UPDATE artifact SET derived_from = ? WHERE id = ?",
                (json.dumps(merged), artifact_id),
            )

    def remove(self, artifact_id: str, delete_file: bool = False) -> None:
        with self._lock, self._conn:
            row = self._fetch_by_id(artifact_id)
            if row is None:
                raise ArtifactNotFound(artifact_id)
            if delete_file:
                try:
                    Path(row[1]).unlink()
                except FileNotFoundError:
                    pass
            self._conn.execute("DELETE FROM artifact WHERE id = ?", (artifact_id,))

    # ---- private ----

    def _fetch_by_id(self, artifact_id: str):
        return self._conn.execute(
            "SELECT * FROM artifact WHERE id = ?", (artifact_id,)
        ).fetchone()

    def _row_to_artifact(self, row) -> Artifact:
        (id_, path, kind, media_type, content_hash, size_bytes, produced_by,
         derived_from_json, goal_id, sub_agent_id, created_at, metadata_json) = row
        return Artifact(
            id=id_,
            path=path,
            kind=kind,
            media_type=media_type,
            content_hash=content_hash,
            size_bytes=size_bytes,
            produced_by=produced_by,
            derived_from=tuple(json.loads(derived_from_json)),
            goal_id=goal_id,
            sub_agent_id=sub_agent_id,
            created_at=created_at,
            metadata=json.loads(metadata_json),
        )


_INSTANCE: ArtifactRegistry | None = None
_INSTANCE_LOCK = Lock()


def get_registry() -> ArtifactRegistry:
    global _INSTANCE
    with _INSTANCE_LOCK:
        if _INSTANCE is None:
            db = Path(os.path.expanduser(
                os.environ.get(
                    "RASPUTIN_OMNITOOL_ARTIFACT_DB",
                    "~/.rasputin/artifacts/registry.db",
                )
            ))
            _INSTANCE = ArtifactRegistry(db)
        return _INSTANCE
