import hashlib
import secrets
import sqlite3
import time
from pathlib import Path

from core.config import get_settings


def _db():
    database_url = get_settings().database_url
    if not database_url.startswith("sqlite:///"):
        raise RuntimeError("Only SQLite DATABASE_URL values are supported; configure sqlite:///...")
    database_path = database_url.removeprefix("sqlite:///")
    Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path, timeout=5, isolation_level=None)
    connection.execute("PRAGMA busy_timeout = 5000")
    connection.execute(
        "CREATE TABLE IF NOT EXISTS keys (hash TEXT PRIMARY KEY, label TEXT, created REAL, revoked INTEGER DEFAULT 0)"
    )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS usage (id INTEGER PRIMARY KEY, key_hash TEXT, endpoint TEXT, created REAL)"
    )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS request_rate_limits ("
        "bucket_key TEXT NOT NULL, window_start INTEGER NOT NULL, count INTEGER NOT NULL, "
        "PRIMARY KEY (bucket_key, window_start))"
    )
    return connection


def digest(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def valid_key(key: str) -> bool:
    if not key:
        return False
    settings = get_settings()
    if settings.api_key and secrets.compare_digest(key, settings.api_key):
        return True
    with _db() as connection:
        return connection.execute(
            "SELECT 1 FROM keys WHERE hash = ? AND revoked = 0", (digest(key),)
        ).fetchone() is not None


def create_key(label: str = "API key"):
    key = "pfx_" + secrets.token_urlsafe(32)
    key_hash = digest(key)
    with _db() as connection:
        connection.execute(
            "INSERT INTO keys(hash, label, created) VALUES (?, ?, ?)",
            (key_hash, label, time.time()),
        )
    return {"id": key_hash[:12], "key": key, "label": label}


def revoke_key(key_id: str) -> bool:
    if not isinstance(key_id, str) or len(key_id) != 12 or any(
        character not in "0123456789abcdef" for character in key_id
    ):
        return False
    with _db() as connection:
        return connection.execute(
            "UPDATE keys SET revoked = 1 WHERE substr(hash, 1, 12) = ?", (key_id,)
        ).rowcount > 0


def record_usage(key: str, endpoint: str):
    with _db() as connection:
        connection.execute(
            "INSERT INTO usage(key_hash, endpoint, created) VALUES (?, ?, ?)",
            (digest(key), endpoint, time.time()),
        )


def consume_rate_limit(bucket_key: str, limit: int, window_seconds: int, now=None):
    """Atomically consume a fixed-window quota shared by workers using this SQLite file."""
    now = time.time() if now is None else now
    window_start = int(now // window_seconds) * window_seconds
    connection = _db()
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "INSERT INTO request_rate_limits(bucket_key, window_start, count) VALUES (?, ?, 1) "
            "ON CONFLICT(bucket_key, window_start) DO UPDATE SET count = count + 1",
            (bucket_key, window_start),
        )
        count = connection.execute(
            "SELECT count FROM request_rate_limits WHERE bucket_key = ? AND window_start = ?",
            (bucket_key, window_start),
        ).fetchone()[0]
        connection.execute(
            "DELETE FROM request_rate_limits WHERE window_start < ?",
            (window_start - max(window_seconds * 2, 86400),),
        )
        connection.commit()
        return count <= limit, count, window_start + window_seconds
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def usage_summary():
    with _db() as connection:
        total = connection.execute("SELECT COUNT(*) FROM usage").fetchone()[0]
        recent = connection.execute(
            "SELECT endpoint, created FROM usage ORDER BY id DESC LIMIT 20"
        ).fetchall()
        keys = connection.execute(
            "SELECT substr(hash, 1, 12), label, created, revoked FROM keys"
        ).fetchall()
    return {
        "total_requests": total,
        "recent": [{"endpoint": endpoint, "created": created} for endpoint, created in recent],
        "keys": [
            {"id": key_id, "label": label, "created": created, "revoked": bool(revoked)}
            for key_id, label, created, revoked in keys
        ],
    }

