from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Set

from aiogram import Bot

from .config import AppConfig, JsonStore
from .linear import LinearClient, extract_github_issue_link, map_assignee_to_mention

logger = logging.getLogger(__name__)


def _store(config: AppConfig) -> JsonStore:
    return JsonStore(config.storage.data_dir)


def get_chats_for_team(team_key: str, config: AppConfig) -> List[int]:
    """Return chat_ids subscribed to this team."""
    result: List[int] = []
    for chat in config.telegram.chats:
        # If chat has no team_keys filter, it receives all teams
        if not chat.team_keys or team_key in chat.team_keys:
            result.append(chat.chat_id)
    return result


async def send_to_chats(
    bot: Bot,
    text: str,
    chat_ids: List[int],
) -> None:
    """Send message to multiple group chats."""
    sent_to: Set[int] = set()
    for chat_id in chat_ids:
        if chat_id not in sent_to:
            try:
                await bot.send_message(chat_id, text, disable_web_page_preview=True)
                sent_to.add(chat_id)
            except Exception as e:
                logger.warning(f"Failed to send to chat {chat_id}: {e}")


async def process_linear_updates(bot: Bot, config: AppConfig) -> None:
    store = _store(config)
    state: Dict = store.get_state()

    last_checked_iso: str = state.get("last_checked_iso")
    initial_run = False
    if last_checked_iso:
        since = datetime.fromisoformat(last_checked_iso)
    else:
        since = datetime.utcnow() - timedelta(minutes=10)
        initial_run = True

    async with LinearClient(config.linear.api_key) as client:
        updated = await client.get_issues_updated_since(
            since, config.linear.team_id, config.linear.team_keys
        )

    assignee_by_id: Dict[str, str] = state.get("assignee_by_id", {})
    state_type_by_id: Dict[str, str] = state.get("state_type_by_id", {})

    for issue in updated:
        issue_id = issue["id"]
        title = issue.get("title")
        url = issue.get("url")
        assignee_name = (issue.get("assignee") or {}).get("name") or ""
        state_type = (issue.get("state") or {}).get("type") or ""
        team_key = (issue.get("team") or {}).get("key") or ""

        # GitHub link suffix
        gh_link = extract_github_issue_link(issue)
        gh_suffix = f" <a href='{gh_link}'>[gh]</a>" if gh_link else ""

        prev_assignee = assignee_by_id.get(issue_id, "")
        prev_state_type = state_type_by_id.get(issue_id, "")

        # Determine target chats for this team
        target_chats = get_chats_for_team(team_key, config)
        if not target_chats:
            logger.debug(f"No chats configured for team {team_key}, skipping issue {issue_id}")

        # Determine if issue is truly new (created after last check)
        created_at_str = issue.get("createdAt")
        is_new_issue = False
        if created_at_str:
            try:
                created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                # Issue is new if created after last_checked (with 1 min buffer for clock skew)
                is_new_issue = created_at >= since - timedelta(seconds=60)
            except (ValueError, TypeError):
                pass

        # New issue notification (only if truly created after last check)
        if is_new_issue and not initial_run and target_chats:
            mention = map_assignee_to_mention(assignee_name, config.linear.assignee_map)
            assignee_part = f" → {mention}" if mention else ""
            text = f"🆕 Создана: <a href='{url}'>{title}</a>{gh_suffix}{assignee_part}\n#linear"
            await send_to_chats(bot, text, target_chats)
        # Assignee change notification (for issues we've seen before)
        elif not is_new_issue and not initial_run and issue_id in assignee_by_id and assignee_name != prev_assignee and target_chats:
            mention = map_assignee_to_mention(assignee_name, config.linear.assignee_map)
            assignee_part = f" → {mention}" if mention else ""
            text = f"🔄 Update: <a href='{url}'>{title}</a>{gh_suffix}{assignee_part}\n#linear"
            await send_to_chats(bot, text, target_chats)

        assignee_by_id[issue_id] = assignee_name

        # Done transition notification (only on change, skip initial snapshot)
        if (
            not initial_run
            and state_type == "completed"
            and prev_state_type != "completed"
        ):
            text = f"✅ Done: <a href='{url}'>{title}</a>{gh_suffix}\n#linear"
            await send_to_chats(bot, text, target_chats)

        state_type_by_id[issue_id] = state_type

    state["assignee_by_id"] = assignee_by_id
    state["state_type_by_id"] = state_type_by_id
    state["last_checked_iso"] = datetime.utcnow().isoformat()
    store.set_state(state)
