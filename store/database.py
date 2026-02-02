"""
SQLite database utilities for the store module.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_SQL = """
CREATE TABLE runs (
  run_id TEXT PRIMARY KEY,
  config_json TEXT NOT NULL,
  seed INTEGER NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE candidates (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  code TEXT NOT NULL,
  code_hash TEXT NOT NULL,
  parent_id TEXT,
  generation INTEGER NOT NULL,
  model_id TEXT NOT NULL,
  signature TEXT,
  status TEXT DEFAULT 'pending',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (run_id) REFERENCES runs(run_id),
  UNIQUE(run_id, code_hash)
);

CREATE TABLE evaluations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  candidate_id TEXT NOT NULL,
  fidelity TEXT NOT NULL,
  score REAL,
  runtime_ms REAL,
  error_type TEXT,
  metadata_json TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (candidate_id) REFERENCES candidates(id)
);

CREATE INDEX idx_candidates_generation ON candidates(run_id, generation);
CREATE INDEX idx_candidates_hash ON candidates(code_hash);
CREATE INDEX idx_evals_candidate ON evaluations(candidate_id);
"""

_IDEMPOTENT_SCHEMA_SQL = (
    SCHEMA_SQL.replace("CREATE TABLE", "CREATE TABLE IF NOT EXISTS")
    .replace("CREATE INDEX", "CREATE INDEX IF NOT EXISTS")
)


def initialize_database(db_path: str) -> None:
    """Create the SQLite database and schema if needed."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path))
    try:
        _ = connection.executescript(_IDEMPOTENT_SCHEMA_SQL)
        connection.commit()
    finally:
        connection.close()


def connect(db_path: str) -> sqlite3.Connection:
    """Open a SQLite connection with sane defaults."""
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    _ = connection.execute("PRAGMA foreign_keys = ON")
    return connection
