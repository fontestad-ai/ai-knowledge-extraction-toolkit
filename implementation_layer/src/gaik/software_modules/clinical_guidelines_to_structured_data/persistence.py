"""Local SQLite persistence for standalone clinical extraction runs."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class ClinicalSQLiteStore:
    """Persist clinical extraction runs and sqlite-vec-ready retrieval records."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS clinical_extraction_runs (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    source_file TEXT NOT NULL,
                    parser_choice TEXT NOT NULL,
                    extraction_backend TEXT NOT NULL,
                    parsed_documents_json TEXT NOT NULL,
                    extracted_knowledge_json TEXT NOT NULL,
                    operationalized_knowledge_json TEXT,
                    validation_json TEXT,
                    quality_report_json TEXT,
                    vector_backend TEXT NOT NULL DEFAULT 'sqlite-vec-ready'
                );

                CREATE TABLE IF NOT EXISTS clinical_atomic_units (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES clinical_extraction_runs(id)
                        ON DELETE CASCADE,
                    semantic_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    normalized_statement TEXT NOT NULL,
                    source_quote TEXT,
                    source_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS clinical_rag_documents (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES clinical_extraction_runs(id)
                        ON DELETE CASCADE,
                    content TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    embedding_json TEXT,
                    vector_backend TEXT NOT NULL DEFAULT 'sqlite-vec-ready'
                );

                CREATE TABLE IF NOT EXISTS clinical_graph_nodes (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES clinical_extraction_runs(id)
                        ON DELETE CASCADE,
                    label TEXT NOT NULL,
                    properties_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS clinical_graph_edges (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES clinical_extraction_runs(id)
                        ON DELETE CASCADE,
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    properties_json TEXT NOT NULL
                );
                """
            )

    def save_run(
        self,
        *,
        source_file: str,
        parser_choice: str,
        extraction_backend: str,
        parsed_documents: list[str],
        extracted_knowledge: list[dict[str, Any]],
        operationalized_knowledge: Any | None,
        validation: Any | None,
        quality_report: Any | None,
    ) -> str:
        run_id = str(uuid.uuid4())
        created_at = datetime.now(UTC).isoformat()
        operationalized = _to_jsonable(operationalized_knowledge)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO clinical_extraction_runs (
                    id, created_at, source_file, parser_choice, extraction_backend,
                    parsed_documents_json, extracted_knowledge_json,
                    operationalized_knowledge_json, validation_json, quality_report_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    created_at,
                    source_file,
                    parser_choice,
                    extraction_backend,
                    json.dumps(parsed_documents),
                    json.dumps(extracted_knowledge, default=str),
                    json.dumps(operationalized, default=str)
                    if operationalized is not None
                    else None,
                    json.dumps(_to_jsonable(validation), default=str)
                    if validation is not None
                    else None,
                    json.dumps(_to_jsonable(quality_report), default=str)
                    if quality_report is not None
                    else None,
                ),
            )
            self._save_operationalized(conn, run_id, operationalized)
        return run_id

    def list_runs(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, created_at, source_file, parser_choice, extraction_backend,
                       quality_report_json, vector_backend
                FROM clinical_extraction_runs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [_row_to_dict(row) for row in rows]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM clinical_extraction_runs WHERE id = ?",
                (run_id,),
            ).fetchone()
            if row is None:
                return None
            payload = _row_to_dict(row)
            for key in (
                "parsed_documents_json",
                "extracted_knowledge_json",
                "operationalized_knowledge_json",
                "validation_json",
                "quality_report_json",
            ):
                payload[key.removesuffix("_json")] = (
                    json.loads(payload[key]) if payload.get(key) else None
                )
            return payload

    @staticmethod
    def _save_operationalized(
        conn: sqlite3.Connection,
        run_id: str,
        operationalized: dict[str, Any] | None,
    ) -> None:
        if not operationalized:
            return
        for unit in operationalized.get("atomic_units", []) or []:
            conn.execute(
                """
                INSERT INTO clinical_atomic_units (
                    id, run_id, semantic_type, title, normalized_statement,
                    source_quote, source_json, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    unit.get("unit_id", str(uuid.uuid4())),
                    run_id,
                    unit.get("semantic_type", "unknown"),
                    unit.get("title", "Untitled clinical unit"),
                    unit.get("normalized_statement", ""),
                    unit.get("source_quote", ""),
                    json.dumps(unit.get("source", {}), default=str),
                    json.dumps(unit.get("metadata", {}), default=str),
                ),
            )
        for index, document in enumerate(operationalized.get("rag_documents", []) or []):
            content = document.get("page_content") or document.get("content") or str(document)
            metadata = document.get("metadata", {})
            conn.execute(
                """
                INSERT INTO clinical_rag_documents (
                    id, run_id, content, metadata_json, embedding_json
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    f"{run_id}:rag:{index}",
                    run_id,
                    content,
                    json.dumps(metadata, default=str),
                    None,
                ),
            )
        graph = operationalized.get("knowledge_graph", {}) or {}
        for node in graph.get("nodes", []) or []:
            conn.execute(
                """
                INSERT INTO clinical_graph_nodes (id, run_id, label, properties_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    node.get("node_id", str(uuid.uuid4())),
                    run_id,
                    node.get("label", "clinical_node"),
                    json.dumps(node, default=str),
                ),
            )
        for index, edge in enumerate(graph.get("edges", []) or []):
            conn.execute(
                """
                INSERT INTO clinical_graph_edges (
                    id, run_id, source_id, target_id, relation_type, properties_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    edge.get("edge_id", f"{run_id}:edge:{index}"),
                    run_id,
                    edge.get("source_id", ""),
                    edge.get("target_id", ""),
                    edge.get("relation_type", "related_to"),
                    json.dumps(edge, default=str),
                ),
            )


def _to_jsonable(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump(mode="json")
        except TypeError:
            return value.model_dump()
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _to_jsonable(item) for key, item in value.items()}
    return value


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}
