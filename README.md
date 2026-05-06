# JEE Forum Management Bot

Production-ready Telegram **forum** management bot for JEE mentorship groups.
Dynamically detects forum topics and categorises messages, tracks 24-hour
activity per student, and posts a daily 3 AM alert digest in the
announcement topic.

Built with `python-telegram-bot` v21, APScheduler, and SQLite. Deploys to
Railway out of the box.

---

## ✨ Features

- **Dynamic forum topic detection** via `message_thread_id` and
  `forum_topic_created` updates — no hardcoded IDs.
- **Auto-detected announcement topic** (matches "announcement", "notice",
  "general"). Used as the destination for `/rule` broadcasts and the daily
  3 AM digest.
- **Keyword-based topic categorisation**: `target`, `screen_time`, `study`,
  `sleep`, `revision`, `completion`, `doubt`.
- **Per-user 24-hour tracking** with alert tiers:
  - 🔴 HIGH ALERT — 0/7
  - 🟠 MID ALERT — 1–3/7
  - 🟡 LOW ALERT — 4–6/7
  - ✅ SAFE — 7/7
- **Daily 3 AM digest** posted to the announcement topic of every group.
- **Admin commands**: `/rule <text>`, `/user @username`, `/report`.
- **Multi-group support** — works in any forum group it's added to.
- **Async**, clean logging, restart-safe SQLite persistence (WAL mode).

---

## 📁 Project structure

```
.
├── main.py            # Entry point + handlers
├── config.py          # Env config + category keywords
├── database.py        # SQLite layer (groups, topics, users, activity)
├── categories.py      # Topic-name → category classifier
├── reports.py         # Daily / per-user report builders
├── scheduler.py       # APScheduler 3 AM cron job
├── requirements.txt
├── Procfile           # Railway worker process
├── railway.json
├── runtime.txt
├── .env.example
└── README.md
```

---

## 🤖 BotFather setup

1. Open [@BotFather](https://t.me/BotFather) in Telegram.
2. `/newbot` → choose a name and username, copy the **token**.
3. **Disable privacy mode** (required so the bot sees every message in topics):
   - `/mybots` → select your bot → **Bot Settings** → **Group Privacy** →
     **Turn off**.
4. Add the bot to your forum supergroup and **promote it to admin** with at
   least: *Manage Topics*, *Send Messages*, *Pin Messages*.

---

## 🔐 Environment variables

Copy `.env.example` → `.env` and fill in:

| Variable        | Required | Default        | Description                              |
|-----------------|:--------:|----------------|------------------------------------------|
| `BOT_TOKEN`     | ✅       | —              | Token from @BotFather                    |
| `DATABASE_PATH` |          | `bot.db`       | SQLite file path                         |
| `TIMEZONE`      |          | `Asia/Kolkata` | Timezone for the daily job               |
| `REPORT_HOUR`   |          | `3`            | Daily report hour (0–23)                 |
| `REPORT_MINUTE` |          | `0`            | Daily report minute                      |
| `LOG_LEVEL`     |          | `INFO`         | `DEBUG` / `INFO` / `WARNING` / `ERROR`   |

---

## 🚀 Local development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # fill in BOT_TOKEN
python main.py
```

---

## ☁️ Railway deployment

1. Push this repo to GitHub.
2. On [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub** → select the repo.
3. In the service **Variables** tab add at least `BOT_TOKEN` (plus any
   overrides from the table above).
4. (Recommended) **Add a Volume** mounted at `/data` and set
   `DATABASE_PATH=/data/bot.db` so the SQLite file survives redeploys.
5. Railway uses `Procfile` (`worker: python main.py`) automatically — the
   bot starts as a long-running worker (no public port needed).
6. Watch the **Deploy Logs** for `Starting bot…` and `Scheduler started`.

`railway.json` sets nixpacks build + restart-on-failure (max 10 retries).

---

## 🗄️ Database schema

SQLite, WAL mode, auto-created on first run.

| Table      | Columns                                                                 | Notes                              |
|------------|-------------------------------------------------------------------------|------------------------------------|
| `groups`   | `chat_id` PK, `title`, `announcement_topic`, `updated_at`               | One row per group                  |
| `topics`   | `(chat_id, topic_id)` PK, `name`, `category`, `updated_at`              | Categorised forum topics           |
| `users`    | `(chat_id, user_id)` PK, `username`, `full_name`                        | Indexed by lowercased `username`   |
| `activity` | `chat_id`, `user_id`, `category`, `ts`                                  | One row per tracked message        |

`activity` is purged daily — rows older than 7 days are removed by the
scheduler after posting the digest.

---

## ⏰ Scheduler logic

- `AsyncIOScheduler` runs a single cron job: every day at
  `REPORT_HOUR:REPORT_MINUTE` in `TIMEZONE`.
- For every known group it builds a digest of the last 24 h, then posts it
  to the group's stored announcement topic (or auto-detects one by name).
- `misfire_grace_time=3600` and `coalesce=True` make the job restart-safe.

---

## 💬 Commands

| Command          | Who    | What it does                                                              |
|------------------|--------|---------------------------------------------------------------------------|
| `/start`,`/help` | Anyone | Help text                                                                 |
| `/rule <text>`   | Admin  | Posts a formatted rule message into the announcement topic                |
| `/user @name`    | Admin  | Shows the user's 24-h score, completed + missing categories, alert tier   |
| `/report`        | Admin  | Posts the full group digest on demand                                     |

---

## 🛠️ Customising categories

Edit `CATEGORY_KEYWORDS` in `config.py`. Order matters — the first keyword
match wins, so place more specific categories (e.g. `completion`) above
broader ones (e.g. `target`).
