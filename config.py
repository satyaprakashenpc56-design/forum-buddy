"""Configuration loaded from environment variables."""
import os
import logging
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
DATABASE_PATH = os.getenv("DATABASE_PATH", "bot.db")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Kolkata")
REPORT_HOUR = int(os.getenv("REPORT_HOUR", "3"))
REPORT_MINUTE = int(os.getenv("REPORT_MINUTE", "0"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Category keyword map. Topic name (lowercased) is searched for these keywords.
# Order matters — first match wins, so put more-specific keywords first.
CATEGORY_KEYWORDS = [
    ("completion",   ["completion", "completed", "done"]),
    ("revision",     ["revision", "revise"]),
    ("target",       ["target", "goal"]),
    ("screen_time",  ["screen time", "screentime", "screen-time"]),
    ("study",        ["study", "studies", "studied"]),
    ("sleep",        ["sleep", "wakeup", "wake up"]),
    ("doubt",        ["doubt", "question", "query"]),
]

# All categories users are tracked against for the daily score (out of N).
TRACKED_CATEGORIES = [c for c, _ in CATEGORY_KEYWORDS]

# Keywords used to auto-detect the announcement topic of a forum.
ANNOUNCEMENT_KEYWORDS = ["announcement", "announce", "notice", "general"]

LOOKBACK_HOURS = 24


def configure_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    )
    # Tame noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)


def validate() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set. Copy .env.example to .env and fill it in.")
