from __future__ import annotations

from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from .config import AppConfig
from .notifier import process_linear_updates
from .reports import send_current_report, send_weekly_stats


async def setup_scheduler(bot: Bot, dp: Dispatcher, config: AppConfig) -> None:
    scheduler = AsyncIOScheduler(timezone=ZoneInfo(config.schedule.timezone))

    hour, minute = map(int, config.schedule.daily_time.split(":"))

    # Schedule daily and weekly reports for EACH configured chat
    for chat in config.telegram.chats:
        # Daily report with pin management
        scheduler.add_job(
            send_current_report,
            trigger=CronTrigger(hour=hour, minute=minute),
            args=[bot, chat.chat_id, config, True, None, chat.team_keys or None],
            id=f"daily_report_{chat.name}",
            replace_existing=True,
        )

        # Weekly report on Sunday 20:00 local time
        scheduler.add_job(
            send_weekly_stats,
            trigger=CronTrigger(day_of_week="sun", hour=20, minute=0),
            args=[bot, chat.chat_id, config, chat.team_keys or None],
            id=f"weekly_stats_{chat.name}",
            replace_existing=True,
        )

    # Frequent poller for Linear updates (assignments and done)
    scheduler.add_job(
        process_linear_updates,
        trigger=IntervalTrigger(seconds=config.schedule.poll_interval_seconds),
        args=[bot, config],
        id="linear_updates_poller",
        replace_existing=True,
    )

    scheduler.start()
