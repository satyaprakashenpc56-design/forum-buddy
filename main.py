"""Telegram Forum Management Bot — entry point."""
from __future__ import annotations

import logging
from typing import Optional

from telegram import Update, ChatMember
from telegram.constants import ChatType, ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config
import database as db
import categories
import reports
from scheduler import start_scheduler

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- helpers
async def _is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.effective_chat or not update.effective_user:
        return False
    try:
        member = await context.bot.get_chat_member(
            update.effective_chat.id, update.effective_user.id
        )
        return member.status in (ChatMember.ADMINISTRATOR, ChatMember.OWNER)
    except Exception:
        log.exception("Admin check failed")
        return False


def _topic_name_from_message(update: Update) -> Optional[str]:
    msg = update.effective_message
    if msg and msg.reply_to_message and msg.reply_to_message.forum_topic_created:
        return msg.reply_to_message.forum_topic_created.name
    return None


# --------------------------------------------------------------------------- handlers
async def on_forum_topic_created(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    chat = update.effective_chat
    if not msg or not chat or not msg.forum_topic_created:
        return
    topic_id = msg.message_thread_id
    name = msg.forum_topic_created.name
    category = categories.classify(name)

    db.upsert_group(chat.id, chat.title)
    db.upsert_topic(chat.id, topic_id, name, category)

    if any(kw in name.lower() for kw in config.ANNOUNCEMENT_KEYWORDS):
        if not db.get_announcement_topic(chat.id):
            db.set_announcement_topic(chat.id, topic_id)
            log.info("Auto-detected announcement topic: %s (%s)", name, topic_id)

    log.info("New topic: chat=%s topic=%s name=%r category=%s", chat.id, topic_id, name, category)


async def on_forum_topic_edited(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    chat = update.effective_chat
    if not msg or not chat or not msg.forum_topic_edited:
        return
    new_name = msg.forum_topic_edited.name
    if new_name:
        db.upsert_topic(chat.id, msg.message_thread_id, new_name, categories.classify(new_name))


async def on_group_message(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Track every message that lands in a forum topic."""
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not msg or not chat or not user or chat.type not in (ChatType.SUPERGROUP, ChatType.GROUP):
        return

    db.upsert_group(chat.id, chat.title)
    db.upsert_user(chat.id, user.id, user.username, user.full_name)

    topic_id = msg.message_thread_id
    if not topic_id:
        return  # general / non-topic message — ignore for category tracking

    topic = db.get_topic(chat.id, topic_id)
    if not topic:
        # Backfill: we might have missed the forum_topic_created update (bot was added later).
        name = _topic_name_from_message(update)
        category = categories.classify(name) if name else None
        db.upsert_topic(chat.id, topic_id, name, category)
        topic = db.get_topic(chat.id, topic_id)

    category = topic["category"] if topic else None
    if category:
        db.log_activity(chat.id, user.id, category)


async def cmd_start(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "👋 JEE Forum Management Bot active.\n\n"
        "Commands (admins only):\n"
        "• /rule <text> — broadcast a rule to the announcement topic\n"
        "• /user @username — show 24h activity of a member"
    )


async def cmd_rule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _is_admin(update, context):
        await update.effective_message.reply_text("❌ Admins only.")
        return
    text = " ".join(context.args).strip()
    if not text:
        await update.effective_message.reply_text("Usage: /rule <rule text>")
        return
    chat = update.effective_chat
    db.upsert_group(chat.id, chat.title)
    topic_id = db.get_announcement_topic(chat.id) or db.find_announcement_topic(
        chat.id, config.ANNOUNCEMENT_KEYWORDS
    )
    body = f"📜 *New Rule*\n\n{text}"
    try:
        await context.bot.send_message(
            chat_id=chat.id, message_thread_id=topic_id, text=body, parse_mode=ParseMode.MARKDOWN,
        )
        await update.effective_message.reply_text("✅ Rule posted.")
    except Exception:
        log.exception("Failed to post rule")
        await update.effective_message.reply_text("⚠️ Could not post to announcement topic.")


async def cmd_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _is_admin(update, context):
        await update.effective_message.reply_text("❌ Admins only.")
        return
    if not context.args:
        await update.effective_message.reply_text("Usage: /user @username")
        return
    chat = update.effective_chat
    row = db.find_user_by_username(chat.id, context.args[0])
    if not row:
        await update.effective_message.reply_text("User not found in this group's tracking.")
        return
    await update.effective_message.reply_text(
        reports.build_user_report(chat.id, row), parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _is_admin(update, context):
        await update.effective_message.reply_text("❌ Admins only.")
        return
    chat = update.effective_chat
    text = reports.build_daily_report(chat.id)
    await update.effective_message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def on_my_chat_member(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat and chat.type in (ChatType.SUPERGROUP, ChatType.GROUP):
        db.upsert_group(chat.id, chat.title)
        log.info("Bot membership change in chat %s (%s)", chat.id, chat.title)


# --------------------------------------------------------------------------- bootstrap
async def _post_init(app: Application) -> None:
    start_scheduler(app)


def build_app() -> Application:
    app = ApplicationBuilder().token(config.BOT_TOKEN).post_init(_post_init).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_start))
    app.add_handler(CommandHandler("rule", cmd_rule))
    app.add_handler(CommandHandler("user", cmd_user))
    app.add_handler(CommandHandler("report", cmd_report))

    app.add_handler(MessageHandler(filters.StatusUpdate.FORUM_TOPIC_CREATED, on_forum_topic_created))
    app.add_handler(MessageHandler(filters.StatusUpdate.FORUM_TOPIC_EDITED, on_forum_topic_edited))
    app.add_handler(
        MessageHandler(
            (filters.ChatType.SUPERGROUP | filters.ChatType.GROUP) & ~filters.StatusUpdate.ALL,
            on_group_message,
        )
    )

    from telegram.ext import ChatMemberHandler
    app.add_handler(ChatMemberHandler(on_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))
    return app


def main() -> None:
    config.configure_logging()
    config.validate()
    db.init_db()
    log.info("Starting bot…")
    app = build_app()
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
