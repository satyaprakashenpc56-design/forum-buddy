"""SQLite persistence layer. Thread-safe via a single connection + lock."""
from __future__ import annotations

import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Iterable, Optional

import config

_lock = threading.RLock()
_conn: Optional[sqlite3.Connection] = None


def init_db() -> None:
    global _conn
    _conn = sqlite3.connect(config.DATABASE_PATH, check_same_thread=False, isolation_level=None)
    _conn.row_factory = sqlite3.Row
    with _lock:
        _conn.executescript(
            """
            PRAGMA journal_mode=WAL;
            PRAGMA synchronous=NORMAL;

            CREATE TABLE IF NOT EXISTS groups (
                chat_id            INTEGER PRIMARY KEY,
                title              TEXT,
                announcement_topic INTEGER,
                updated_at         INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS topics (
                chat_id      INTEGER NOT NULL,
                topic_id     INTEGER NOT NULL,
                name         TEXT,
                category     TEXT,
                updated_at   INTEGER NOT NULL,
                PRIMARY KEY (chat_id, topic_id)
            );

            CREATE TABLE IF NOT EXISTS users (
                chat_id   INTEGER NOT NULL,
                user_id   INTEGER NOT NULL,
                username  TEXT,
                full_name TEXT,
                PRIMARY KEY (chat_id, user_id)
            );
            CREATE INDEX IF NOT EXISTS idx_users_username
                ON users (chat_id, lower(username));

            CREATE TABLE IF NOT EXISTS activity (
                chat_id    INTEGER NOT NULL,
                user_id    INTEGER NOT NULL,
                category   TEXT    NOT NULL,
                ts         INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_activity_lookup
                ON activity (chat_id, user_id, ts);
            CREATE INDEX IF NOT EXISTS idx_activity_chat_ts
                ON activity (chat_id, ts);
            """
        )


@contextmanager
def _cursor():
    assert _conn is not None, "Database not initialised — call init_db() first."
    with _lock:
        cur = _conn.cursor()
        try:
            yield cur
        finally:
            cur.close()


# --------------------------------------------------------------------------- groups
def upsert_group(chat_id: int, title: Optional[str]) -> None:
    with _cursor() as c:
        c.execute(
            """INSERT INTO groups (chat_id, title, updated_at) VALUES (?, ?, ?)
               ON CONFLICT(chat_id) DO UPDATE SET title=excluded.title, updated_at=excluded.updated_at""",
            (chat_id, title, int(time.time())),
        )


def set_announcement_topic(chat_id: int, topic_id: int) -> None:
    with _cursor() as c:
        c.execute(
            "UPDATE groups SET announcement_topic = ?, updated_at = ? WHERE chat_id = ?",
            (topic_id, int(time.time()), chat_id),
        )


def get_announcement_topic(chat_id: int) -> Optional[int]:
    with _cursor() as c:
        row = c.execute(
            "SELECT announcement_topic FROM groups WHERE chat_id = ?", (chat_id,)
        ).fetchone()
        return row["announcement_topic"] if row else None


def all_groups() -> list[sqlite3.Row]:
    with _cursor() as c:
        return c.execute("SELECT * FROM groups").fetchall()


# --------------------------------------------------------------------------- topics
def upsert_topic(chat_id: int, topic_id: int, name: Optional[str], category: Optional[str]) -> None:
    with _cursor() as c:
        c.execute(
            """INSERT INTO topics (chat_id, topic_id, name, category, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(chat_id, topic_id) DO UPDATE SET
                   name=excluded.name, category=excluded.category, updated_at=excluded.updated_at""",
            (chat_id, topic_id, name, category, int(time.time())),
        )


def get_topic(chat_id: int, topic_id: int) -> Optional[sqlite3.Row]:
    with _cursor() as c:
        return c.execute(
            "SELECT * FROM topics WHERE chat_id = ? AND topic_id = ?",
            (chat_id, topic_id),
        ).fetchone()


def find_announcement_topic(chat_id: int, keywords: Iterable[str]) -> Optional[int]:
    with _cursor() as c:
        rows = c.execute(
            "SELECT topic_id, name FROM topics WHERE chat_id = ?", (chat_id,)
        ).fetchall()
    for kw in keywords:
        for r in rows:
            if r["name"] and kw in r["name"].lower():
                return r["topic_id"]
    return None


# --------------------------------------------------------------------------- users
def upsert_user(chat_id: int, user_id: int, username: Optional[str], full_name: Optional[str]) -> None:
    with _cursor() as c:
        c.execute(
            """INSERT INTO users (chat_id, user_id, username, full_name) VALUES (?, ?, ?, ?)
               ON CONFLICT(chat_id, user_id) DO UPDATE SET
                   username=excluded.username, full_name=excluded.full_name""",
            (chat_id, user_id, username, full_name),
        )


def find_user_by_username(chat_id: int, username: str) -> Optional[sqlite3.Row]:
    uname = username.lstrip("@").lower()
    with _cursor() as c:
        return c.execute(
            "SELECT * FROM users WHERE chat_id = ? AND lower(username) = ?",
            (chat_id, uname),
        ).fetchone()


def all_users(chat_id: int) -> list[sqlite3.Row]:
    with _cursor() as c:
        return c.execute("SELECT * FROM users WHERE chat_id = ?", (chat_id,)).fetchall()


# --------------------------------------------------------------------------- activity
def log_activity(chat_id: int, user_id: int, category: str, ts: Optional[int] = None) -> None:
    with _cursor() as c:
        c.execute(
            "INSERT INTO activity (chat_id, user_id, category, ts) VALUES (?, ?, ?, ?)",
            (chat_id, user_id, category, ts or int(time.time())),
        )


def categories_in_window(chat_id: int, user_id: int, since_ts: int) -> set[str]:
    with _cursor() as c:
        rows = c.execute(
            "SELECT DISTINCT category FROM activity WHERE chat_id=? AND user_id=? AND ts >= ?",
            (chat_id, user_id, since_ts),
        ).fetchall()
    return {r["category"] for r in rows}


def purge_older_than(ts: int) -> int:
    with _cursor() as c:
        c.execute("DELETE FROM activity WHERE ts < ?", (ts,))
        return c.rowcount
