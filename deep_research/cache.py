"""SQLite-backed TTL cache utilities."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any

# Repository root (parent of `deep_research/`) for stable relative cache paths.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def resolve_cache_db_path(
    path: str,
    anchor: str | Path | None = None,
) -> str:
    """Make cache DB path absolute.

    Relative paths resolve under ``anchor`` (directory containing config.yaml when set),
    else the process cwd, else the package tree (last resort for tests).
    """
    p = Path(path)
    if p.is_absolute():
        return str(p.resolve())
    if anchor:
        return str((Path(anchor).resolve() / p).resolve())
    try:
        return str((Path.cwd().resolve() / p).resolve())
    except Exception:
        return str((_PROJECT_ROOT / p).resolve())


def append_cache_write_log(message: str, *, db_path: str | None = None) -> None:
    """Append one line to cache_writes.log beside the SQLite file (not package install dir).

    When deep_research is imported from site-packages, Path(__file__).parent.parent is wrong
    for the user's project; using db_path keeps logs next to the DB you actually write.
    """
    import sys

    try:
        if db_path:
            base = Path(db_path).resolve().parent
        else:
            base = _PROJECT_ROOT / ".cache"
        base.mkdir(parents=True, exist_ok=True)
        log_path = base / "cache_writes.log"
        ts = time.strftime("%Y-%m-%dT%H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"{ts} {message}\n")
    except Exception as e:
        try:
            print(f"[cache] append_cache_write_log failed: {e}", file=sys.stderr, flush=True)
        except Exception:
            pass


def json_safe_for_cache(obj: Any) -> Any:
    """Recursively convert values so json.dumps succeeds (search tool payloads may hold odd types)."""
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, dict):
        return {str(k): json_safe_for_cache(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe_for_cache(x) for x in obj]
    if isinstance(obj, (bytes, bytearray)):
        return obj.decode("utf-8", errors="replace")
    return str(obj)


def stable_cache_key(prefix: str, payload: dict[str, Any]) -> str:
    """Build a stable SHA256 cache key from a prefix + JSON payload."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    return f"{prefix}:{digest}"


# Longer timeout: parallel section workers hit the same DB concurrently.
_SQLITE_TIMEOUT_S = 30.0


def _sqlite_connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=_SQLITE_TIMEOUT_S)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=60000")
    except Exception:
        pass
    return conn


class SQLiteTTLCache:
    """Small fail-open SQLite cache with per-item TTL."""

    def __init__(self, db_path: str, cleanup_probability: float = 0.01) -> None:
        self.db_path = str(db_path)
        self.cleanup_probability = max(0.0, min(1.0, cleanup_probability))
        self._ensure_db()

    def _ensure_db(self) -> None:
        path = Path(self.db_path)
        if path.parent:
            path.parent.mkdir(parents=True, exist_ok=True)
        with _sqlite_connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_entries (
                    cache_key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    expires_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cache_entries_expires_at ON cache_entries(expires_at)"
            )
            conn.commit()

    def get(self, key: str) -> Any | None:
        now = int(time.time())
        with _sqlite_connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT value_json, expires_at FROM cache_entries WHERE cache_key = ?",
                (key,),
            ).fetchone()
            if row is None:
                return None
            value_json, expires_at = row
            if int(expires_at) <= now:
                conn.execute("DELETE FROM cache_entries WHERE cache_key = ?", (key,))
                conn.commit()
                return None
            try:
                return json.loads(value_json)
            except json.JSONDecodeError:
                conn.execute("DELETE FROM cache_entries WHERE cache_key = ?", (key,))
                conn.commit()
                return None

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        ttl = max(1, int(ttl_seconds))
        now = int(time.time())
        expires_at = now + ttl
        safe = json_safe_for_cache(value)
        value_json = json.dumps(safe, ensure_ascii=True, default=str)
        with _sqlite_connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO cache_entries(cache_key, value_json, expires_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    value_json=excluded.value_json,
                    expires_at=excluded.expires_at,
                    updated_at=excluded.updated_at
                """,
                (key, value_json, expires_at, now),
            )
            if self.cleanup_probability > 0.0:
                if (int.from_bytes(hashlib.sha256(f"{key}:{now}".encode()).digest()[:2], "big") / 65535.0) < self.cleanup_probability:
                    conn.execute("DELETE FROM cache_entries WHERE expires_at <= ?", (now,))
            conn.commit()

    def delete_expired(self) -> int:
        now = int(time.time())
        with _sqlite_connect(self.db_path) as conn:
            cur = conn.execute("DELETE FROM cache_entries WHERE expires_at <= ?", (now,))
            conn.commit()
            return int(cur.rowcount or 0)

    def count_entries(self) -> int:
        """Return number of rows in the cache table (including expired keys until cleaned)."""
        try:
            with _sqlite_connect(self.db_path) as conn:
                row = conn.execute("SELECT COUNT(*) FROM cache_entries").fetchone()
                return int(row[0]) if row and row[0] is not None else 0
        except Exception:
            return -1
