"""SQLite-backed cache with TTL support."""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


def platform_cache_dir() -> Path:
    """Return the platform-appropriate cache directory."""
    import os
    import sys

    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA", "")
        if base:
            return Path(base) / "insecure-tree" / "Cache"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "insecure-tree"

    xdg = os.environ.get("XDG_CACHE_HOME", "")
    if xdg:
        return Path(xdg) / "insecure-tree"
    return Path.home() / ".cache" / "insecure-tree"


class Cache:
    """Thread-safe SQLite cache keyed by domain+sha256(key)."""

    _CREATE = """
    CREATE TABLE IF NOT EXISTS cache (
        domain TEXT NOT NULL,
        key_hash TEXT NOT NULL,
        value TEXT NOT NULL,
        expires_at REAL NOT NULL,
        PRIMARY KEY (domain, key_hash)
    )
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        if path is None:
            path = platform_cache_dir() / "cache.db"
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
        return self._conn

    def _init_db(self) -> None:
        try:
            with self._lock:
                conn = self._connect()
                conn.execute(self._CREATE)
                conn.commit()
        except Exception as exc:
            log.warning("Cache init failed: %s", exc)

    @staticmethod
    def _hash(key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()

    def get(self, domain: str, key: str) -> Optional[str]:
        """Return cached value or None if missing/expired."""
        try:
            with self._lock:
                conn = self._connect()
                row = conn.execute(
                    "SELECT value, expires_at FROM cache WHERE domain=? AND key_hash=?",
                    (domain, self._hash(key)),
                ).fetchone()
            if row is None:
                return None
            value, expires_at = row
            if expires_at < time.time():
                return None
            return str(value)
        except Exception as exc:
            log.debug("Cache get error: %s", exc)
            return None

    def put(self, domain: str, key: str, value: str, ttl_seconds: int) -> None:
        """Store a value with a TTL."""
        try:
            with self._lock:
                conn = self._connect()
                conn.execute(
                    "INSERT OR REPLACE INTO cache (domain, key_hash, value, expires_at) VALUES (?,?,?,?)",
                    (domain, self._hash(key), value, time.time() + ttl_seconds),
                )
                conn.commit()
        except Exception as exc:
            log.debug("Cache put error: %s", exc)

    def put_json(self, domain: str, key: str, value: object, ttl_seconds: int) -> None:
        self.put(domain, key, json.dumps(value), ttl_seconds)

    def get_json(self, domain: str, key: str) -> Optional[object]:
        raw = self.get(domain, key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def evict_older_than(self, seconds: int) -> int:
        """Delete entries older than `seconds`. Returns count deleted."""
        cutoff = time.time() - seconds
        try:
            with self._lock:
                conn = self._connect()
                cur = conn.execute("DELETE FROM cache WHERE expires_at < ?", (cutoff,))
                conn.commit()
                return cur.rowcount
        except Exception as exc:
            log.warning("Cache evict error: %s", exc)
            return 0

    def clean(self) -> int:
        """Delete all expired entries."""
        try:
            with self._lock:
                conn = self._connect()
                cur = conn.execute("DELETE FROM cache WHERE expires_at < ?", (time.time(),))
                conn.commit()
                return cur.rowcount
        except Exception as exc:
            log.warning("Cache clean error: %s", exc)
            return 0

    def clear_all(self) -> None:
        try:
            with self._lock:
                conn = self._connect()
                conn.execute("DELETE FROM cache")
                conn.commit()
        except Exception as exc:
            log.warning("Cache clear error: %s", exc)

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
