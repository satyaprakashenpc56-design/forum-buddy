"""Daily report generation."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterable

import config
import database as db


@dataclass
class UserStatus:
    user_id: int
    display: str
    done: set[str]
    missing: list[str]
    total: int

    @property
    def completed(self) -> int:
        return len(self.done)

    @property
    def percent(self) -> int:
        return round(100 * self.completed / self.total) if self.total else 0

    @property
    def alert(self) -> str:
        if self.completed == self.total:
            return "✅ SAFE"
        if self.completed == 0:
            return "🔴 HIGH ALERT"
        if self.completed <= 3:
            return "🟠 MID ALERT"
        return "🟡 LOW ALERT"


def _display(row) -> str:
    if row["username"]:
        return f"@{row['username']}"
    return row["full_name"] or f"user{row['user_id']}"


def status_for_user(chat_id: int, user_row, since_ts: int) -> UserStatus:
    tracked = config.TRACKED_CATEGORIES
    done = db.categories_in_window(chat_id, user_row["user_id"], since_ts) & set(tracked)
    missing = [c for c in tracked if c not in done]
    return UserStatus(
        user_id=user_row["user_id"],
        display=_display(user_row),
        done=done,
        missing=missing,
        total=len(tracked),
    )


def build_daily_report(chat_id: int) -> str:
    since = int(time.time()) - config.LOOKBACK_HOURS * 3600
    users = db.all_users(chat_id)
    if not users:
        return "📊 *Daily Activity Report*\n\nNo tracked users yet."

    statuses = [status_for_user(chat_id, u, since) for u in users]
    statuses.sort(key=lambda s: (s.completed, s.display.lower()))

    lines = ["📊 *Daily Activity Report (last 24h)*", ""]
    for s in statuses:
        lines.append(
            f"{s.alert} — {s.display}  `{s.completed}/{s.total}` ({s.percent}%)"
        )
        if s.missing:
            lines.append(f"   • Missing: {', '.join(s.missing)}")
    return "\n".join(lines)


def build_user_report(chat_id: int, user_row) -> str:
    since = int(time.time()) - config.LOOKBACK_HOURS * 3600
    s = status_for_user(chat_id, user_row, since)
    done = ", ".join(sorted(s.done)) or "—"
    missing = ", ".join(s.missing) or "—"
    return (
        f"👤 *{s.display}* (last 24h)\n"
        f"Status: {s.alert}\n"
        f"Score: `{s.completed}/{s.total}` ({s.percent}%)\n"
        f"✅ Done: {done}\n"
        f"❌ Missing: {missing}"
    )
