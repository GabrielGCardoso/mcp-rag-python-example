import sqlite3
import sys
from array import array
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from lib.config import SQLITE_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
  -- repository
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  last_crawl_at TEXT,
  -- commit_sha
  last_commit TEXT,
  last_error TEXT,
  chunk_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS files (
  -- repository
  source_id TEXT NOT NULL,
  -- path
  path TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  embed_model TEXT NOT NULL,
  embed_dim INTEGER NOT NULL,
  -- commit_sha
  commit_sha TEXT,
  PRIMARY KEY (source_id, path)
);

CREATE TABLE IF NOT EXISTS chunks (
  id INTEGER PRIMARY KEY,
  -- repository
  source_id TEXT NOT NULL,
  -- path
  path TEXT NOT NULL,
  chunk_index INTEGER NOT NULL,
  text TEXT NOT NULL,
  embedding BLOB NOT NULL,
  embed_model TEXT NOT NULL,
  UNIQUE (source_id, path, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunks_source_model
  ON chunks (source_id, embed_model);
"""


def pack_embedding(values: list[float]) -> bytes:
    buf = array("f", values)
    if sys.byteorder != "little":
        buf.byteswap()
    return buf.tobytes()


def unpack_embedding(blob: bytes) -> list[float]:
    buf = array("f")
    buf.frombytes(blob)
    if sys.byteorder != "little":
        buf.byteswap()
    return list(buf)


@contextmanager
def connect(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    db_path = Path(path) if path is not None else SQLITE_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.executescript(SCHEMA)
        yield conn
    finally:
        conn.close()


def get_file(conn: sqlite3.Connection, source_id: str, path: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT content_hash, embed_model, embed_dim
        FROM files
        WHERE source_id = ? AND path = ?
        """,
        (source_id, path),
    ).fetchone()


def list_paths(conn: sqlite3.Connection, source_id: str) -> set[str]:
    rows = conn.execute(
        "SELECT path FROM files WHERE source_id = ?",
        (source_id,),
    ).fetchall()
    return {row["path"] for row in rows}


def replace_file(
    conn: sqlite3.Connection,
    *,
    source_id: str,
    path: str,
    content_hash: str,
    embed_model: str,
    embed_dim: int,
    commit_sha: str | None,
    chunks: list[tuple[int, str, bytes]],
) -> None:
    with conn:
        conn.execute(
            "DELETE FROM chunks WHERE source_id = ? AND path = ?",
            (source_id, path),
        )
        conn.execute(
            "DELETE FROM files WHERE source_id = ? AND path = ?",
            (source_id, path),
        )
        conn.execute(
            """
            INSERT INTO files (
              source_id, path, content_hash, embed_model, embed_dim, commit_sha
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (source_id, path, content_hash, embed_model, embed_dim, commit_sha),
        )
        conn.executemany(
            """
            INSERT INTO chunks (
              source_id, path, chunk_index, text, embedding, embed_model
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (source_id, path, index, text, blob, embed_model)
                for index, text, blob in chunks
            ],
        )


def delete_file(conn: sqlite3.Connection, source_id: str, path: str) -> None:
    with conn:
        conn.execute(
            "DELETE FROM chunks WHERE source_id = ? AND path = ?",
            (source_id, path),
        )
        conn.execute(
            "DELETE FROM files WHERE source_id = ? AND path = ?",
            (source_id, path),
        )


def record_source(
    conn: sqlite3.Connection,
    *,
    source_id: str,
    kind: str,
    crawled_at: str,
    commit_sha: str | None,
    error: str | None,
) -> int:
    count = conn.execute(
        "SELECT COUNT(*) AS n FROM chunks WHERE source_id = ?",
        (source_id,),
    ).fetchone()["n"]
    with conn:
        conn.execute(
            """
            INSERT INTO sources (id, kind, last_crawl_at, last_commit, last_error, chunk_count)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              kind = excluded.kind,
              last_crawl_at = excluded.last_crawl_at,
              last_commit = excluded.last_commit,
              last_error = excluded.last_error,
              chunk_count = excluded.chunk_count
            """,
            (source_id, kind, crawled_at, commit_sha, error, count),
        )
    return count


def chunk_counts(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        "SELECT source_id, COUNT(*) AS n FROM chunks GROUP BY source_id"
    ).fetchall()
    return {row["source_id"]: row["n"] for row in rows}


def source_rows(conn: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    rows = conn.execute("SELECT * FROM sources").fetchall()
    return {row["id"]: row for row in rows}


def load_chunks(
    conn: sqlite3.Connection,
    embed_model: str,
    source_ids: list[str] | None,
) -> list[dict[str, Any]]:
    if source_ids is not None and not source_ids:
        return []

    sql = """
        SELECT source_id, path, chunk_index, text, embedding
        FROM chunks
        WHERE embed_model = ?
    """
    params: list[Any] = [embed_model]
    if source_ids is not None:
        placeholders = ", ".join("?" for _ in source_ids)
        sql += f" AND source_id IN ({placeholders})"
        params.extend(source_ids)

    docs: list[dict[str, Any]] = []
    expected_dim: int | None = None
    for row in conn.execute(sql, params):
        embedding = unpack_embedding(row["embedding"])
        if expected_dim is None:
            expected_dim = len(embedding)
        elif len(embedding) != expected_dim:
            raise RuntimeError(
                "Há vetores de dimensões diferentes para o modelo "
                f"{embed_model}. Rode o crawl de novo para reindexar."
            )
        docs.append(
            {
                "text": row["text"],
                "embedding": embedding,
                "metadata": {
                    "source_id": row["source_id"],
                    "path": row["path"],
                    "chunk_index": row["chunk_index"],
                },
            }
        )
    return docs
