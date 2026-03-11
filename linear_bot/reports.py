from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from aiogram import Bot

from .config import AppConfig, JsonStore
from .linear import LinearClient, map_assignee_to_mention


def _store(config: AppConfig) -> JsonStore:
    return JsonStore(config.storage.data_dir)


def _start_of_calendar_week_utc(tz_name: str) -> datetime:
    tz = ZoneInfo(tz_name)
    now_local = datetime.now(tz)
    week_start_local = datetime.combine(
        (now_local - timedelta(days=now_local.weekday())).date(), time(0, 0), tz
    )
    return week_start_local.astimezone(ZoneInfo("UTC"))


def _chat_internal_link(chat_id: int, message_id: int) -> str:
    # Works for supergroups: -100XXXXXXXXXX → https://t.me/c/XXXXXXXXXX/<message_id>
    s = str(chat_id)
    if s.startswith("-100"):
        cid = s[4:]
    else:
        cid = s.lstrip("-")
    return f"https://t.me/c/{cid}/{message_id}"


async def send_current_report(
    bot: Bot,
    chat_id: int,
    config: AppConfig,
    pin: bool = False,
    reply_to_message_id: Optional[int] = None,
    team_keys_filter: Optional[List[str]] = None,
) -> None:
    week_start_utc = _start_of_calendar_week_utc(config.schedule.timezone)
    # Use team_keys_filter if provided, otherwise fall back to config.linear.team_keys
    effective_keys = team_keys_filter if team_keys_filter else config.linear.team_keys
    async with LinearClient(config.linear.api_key) as client:
        done = await client.get_done_issues_since(
            week_start_utc, config.linear.team_id, effective_keys
        )
        inprog = await client.get_in_progress_issues(
            config.linear.team_id, effective_keys, config.linear.include_unstarted
        )

    total = len(done) + len(inprog)
    percent = round((len(done) / total * 100.0), 1) if total else 0.0

    # Group in-progress by assignee
    grouped: Dict[str, List[dict]] = {}
    for i in inprog:
        assignee_name = (i.get("assignee") or {}).get("name")
        team_key = (i.get("team") or {}).get("key") or ""

        if assignee_name:
            mention = map_assignee_to_mention(assignee_name, config.linear.assignee_map)
        else:
            # Unassigned - check if team has an owner
            mention = config.telegram.team_owner_mention.get(team_key, "Unassigned")

        grouped.setdefault(mention, []).append(i)

    lines: List[str] = []
    lines.append("<b>Daily Report</b>")
    # Summary line
    lines.append(f"<b>Summary:</b> Done {len(done)} / Total {total} ({percent}%)")
    # Previous pin link if exists
    store = _store(config)
    pins = store.get_pins()
    old = pins.get("daily")
    if old:
        try:
            link = _chat_internal_link(chat_id, old)
            lines.append(f"Previous: <a href='{link}'>link</a>")
        except Exception:
            pass

    # Done
    lines.append("<b>Done</b>")
    for i in done:
        lines.append(f"✓ <a href='{i['url']}'>{i['title']}</a>")

    # In Progress grouped
    lines.append("\n<b>In Progress</b>")
    for assignee, items in grouped.items():
        lines.append(f"— <i>{assignee}</i>")
        for i in items:
            lines.append(f"  • <a href='{i['url']}'>{i['title']}</a>")

    lines.append("\n#linear")
    text = "\n".join(lines)

    msg = await bot.send_message(
        chat_id,
        text,
        disable_web_page_preview=True,
        reply_to_message_id=reply_to_message_id,
    )
    if pin:
        if old:
            try:
                await bot.unpin_chat_message(chat_id=chat_id, message_id=old)
            except Exception:
                pass
        try:
            await bot.pin_chat_message(
                chat_id=chat_id, message_id=msg.message_id, disable_notification=True
            )
            pins["daily"] = msg.message_id
            store.set_pins(pins)
        except Exception:
            pass


async def send_weekly_stats(
    bot: Bot,
    chat_id: int,
    config: AppConfig,
    team_keys_filter: Optional[List[str]] = None,
) -> None:
    week_start_utc = _start_of_calendar_week_utc(config.schedule.timezone)
    # Use team_keys_filter if provided, otherwise fall back to config.linear.team_keys
    effective_keys = team_keys_filter if team_keys_filter else config.linear.team_keys
    async with LinearClient(config.linear.api_key) as client:
        done = await client.get_done_issues_since(
            week_start_utc, config.linear.team_id, effective_keys
        )
        inprog = await client.get_in_progress_issues(
            config.linear.team_id, effective_keys, config.linear.include_unstarted
        )

    total = len(done) + len(inprog)
    percent = round((len(done) / total * 100.0), 1) if total else 0.0

    lines: List[str] = []
    lines.append("<b>Weekly Report</b>")
    lines.append(f"<b>Summary:</b> Done {len(done)} / Total {total} ({percent}%)")
    lines.append("<b>Done</b>")
    for i in done:
        lines.append(f"✓ <a href='{i['url']}'>{i['title']}</a>")
    lines.append("\n<b>In Progress</b>")
    for i in inprog:
        lines.append(f"• <a href='{i['url']}'>{i['title']}</a>")
    lines.append("\n#linear")
    text = "\n".join(lines)
    await bot.send_message(chat_id, text, disable_web_page_preview=True)


async def send_personal_tasks(
    bot: Bot,
    chat_id: int,
    user,
    config: AppConfig,
    reply_to_message_id: Optional[int] = None,
) -> None:
    target_tg = user.username or ""
    reverse = {v: k for k, v in config.linear.assignee_map.items()}
    linear_name: Optional[str] = reverse.get(target_tg)

    async with LinearClient(config.linear.api_key) as client:
        issues = await client.get_in_progress_issues(
            config.linear.team_id,
            config.linear.team_keys,
            config.linear.include_unstarted,
        )

    filtered = [
        i for i in issues if (i.get("assignee") or {}).get("name") == linear_name
    ]
    if not filtered:
        await bot.send_message(chat_id, "No personal tasks found.")
        return
    lines = [f"<b>Tasks for @{target_tg}</b>"]
    for i in filtered:
        lines.append(f"• <a href='{i['url']}'>{i['title']}</a>")
    lines.append("\n#linear")
    await bot.send_message(
        chat_id,
        "\n".join(lines),
        disable_web_page_preview=True,
        reply_to_message_id=reply_to_message_id,
    )
