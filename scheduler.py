"""APScheduler setup for the daily 3 AM alert job."""
from __future__ import annotations

import logging
import time

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.constants import ParseMode
from telegram.ext import Application

import config
import database as db
import reports

log = logging.getLogger(__name__)


async def _run_daily_reports(app: Application) -> None:
    log.info("Running daily report job")
    for group in db.all_groups():
        chat_id = group["chat_id"]
        topic_id = group["announcement_topic"] or db.find_announcement_topic(
            chat_id, config.ANNOUNCEMENT_KEYWORDS
        )
        try:
            text = reports.build_daily_report(chat_id)
            await app.bot.send_message(
                chat_id=chat_id,
                message_thread_id=topic_id,
                text=text,
                parse_mode=ParseMode.MARKDOWN,
            )
            log.info("Sent daily report to chat %s (topic=%s)", chat_id, topic_id)
        except Exception:
            log.exception("Failed to send daily report to chat %s", chat_id)

    # Housekeeping: purge activity older than 7 days
    cutoff = int(time.time()) - 7 * 24 * 3600
    deleted = db.purge_older_than(cutoff)
    if deleted:
        log.info("Purged %d old activity rows", deleted)


def start_scheduler(app: Application) -> AsyncIOScheduler:
    tz = pytz.timezone(config.TIMEZONE)
    scheduler = AsyncIOScheduler(timezone=tz)
    scheduler.add_job(
        _run_daily_reports,
        trigger="cron",
        hour=config.REPORT_HOUR,
        minute=config.REPORT_MINUTE,
        args=[app],
        id="daily_report",
        replace_existing=True,
        misfire_grace_time=3600,
        coalesce=True,
    )
    scheduler.start()
    log.info(
        "Scheduler started — daily report at %02d:%02d %s",
        config.REPORT_HOUR, config.REPORT_MINUTE, config.TIMEZONE,
    )
    return scheduler
