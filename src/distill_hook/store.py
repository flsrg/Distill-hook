from __future__ import annotations

import hashlib
import os
import sqlite3
import time
import zlib
from pathlib import Path

DEFAULT_TTL_DAYS = 7
DEFAULT_MAX_BYTES = 50 * 1024 * 1024


def default_store_path() -> Path:
    override = os.environ.get("DISTILL_HOOK_STORE")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".codex" / "distill-hook" / "omissions.db"


class OmissionStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_store_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA busy_timeout=3000")
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS omissions (
                ref TEXT PRIMARY KEY,
                content BLOB NOT NULL,
                command TEXT NOT NULL,
                created_at REAL NOT NULL,
                raw_bytes INTEGER NOT NULL,
                access_count INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        self.conn.commit()

    def __enter__(self) -> "OmissionStore":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def close(self) -> None:
        self.conn.close()

    def put(self, content: bytes, command: str) -> str:
        digest = hashlib.sha256(content).hexdigest()[:16]
        compressed = zlib.compress(content, level=6)
        existing = self.conn.execute(
            "SELECT content FROM omissions WHERE ref = ?", (digest,)
        ).fetchone()
        if existing is not None and zlib.decompress(existing[0]) != content:
            digest = hashlib.sha256(content + os.urandom(16)).hexdigest()[:16]
        self.conn.execute(
            """
            INSERT INTO omissions(ref, content, command, created_at, raw_bytes, access_count)
            VALUES (?, ?, ?, ?, ?, 0)
            ON CONFLICT(ref) DO UPDATE SET created_at = excluded.created_at
            """,
            (digest, compressed, command, time.time(), len(content)),
        )
        self.conn.commit()
        return digest

    def get(self, ref: str) -> bytes | None:
        row = self.conn.execute(
            "SELECT content FROM omissions WHERE ref = ?", (ref,)
        ).fetchone()
        if row is None:
            return None
        self.conn.execute(
            "UPDATE omissions SET access_count = access_count + 1 WHERE ref = ?", (ref,)
        )
        self.conn.commit()
        return zlib.decompress(row[0])

    def prune(
        self,
        *,
        ttl_days: int = DEFAULT_TTL_DAYS,
        max_bytes: int = DEFAULT_MAX_BYTES,
    ) -> None:
        cutoff = time.time() - ttl_days * 86400
        self.conn.execute("DELETE FROM omissions WHERE created_at < ?", (cutoff,))
        self.conn.commit()

        rows = self.conn.execute(
            "SELECT ref, length(content), created_at FROM omissions ORDER BY created_at ASC"
        ).fetchall()
        total = sum(int(row[1]) for row in rows)
        for ref, size, _created in rows:
            if total <= max_bytes:
                break
            self.conn.execute("DELETE FROM omissions WHERE ref = ?", (ref,))
            total -= int(size)
        self.conn.commit()
