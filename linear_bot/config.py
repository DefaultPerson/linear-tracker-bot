from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ChatConfig(BaseModel):
    """Single chat configuration with team mappings."""

    name: str  # Friendly name (e.g., "chat1")
    chat_id: int  # Telegram chat ID
    team_keys: List[str] = Field(default_factory=list)  # Teams that notify this chat


class TelegramConfig(BaseModel):
    token: str
    group_id: Optional[int] = None  # DEPRECATED: kept for backward compat
    chats: List[ChatConfig] = Field(default_factory=list)  # Multi-chat config
    allowed_users: List[int] = Field(default_factory=list)  # DM-enabled user IDs
    admin_users: List[int] = Field(
        default_factory=list
    )  # Admin user IDs (can impersonate)
    user_assignee_map: Dict[int, str] = Field(
        default_factory=dict
    )  # tg_id -> Linear assignee name
    team_dm_map: Dict[str, List[int]] = Field(
        default_factory=dict
    )  # team_key -> list of tg_ids to notify
    team_owner_mention: Dict[str, str] = Field(
        default_factory=dict
    )  # team_key -> @username for display in reports


class LinearConfig(BaseModel):
    api_key: str
    team_id: Optional[str] = None
    team_keys: Optional[List[str]] = None
    org_id: Optional[str] = None
    include_unstarted: bool = (
        False  # Include "unstarted" state in addition to "started"
    )
    assignee_map: Dict[str, str] = Field(
        default_factory=dict
    )  # Linear name -> telegram username (no @)


class ScheduleConfig(BaseModel):
    timezone: str = "UTC"
    daily_time: str = "08:00"  # HH:MM 24h
    weekly_cron: str = "0 0 * * MON"  # At 00:00 on Monday
    poll_interval_seconds: int = 60


class StorageConfig(BaseModel):
    data_dir: str = "bots/linear-bot/data"


class AppConfig(BaseModel):
    telegram: TelegramConfig
    linear: LinearConfig
    schedule: ScheduleConfig = ScheduleConfig()
    storage: StorageConfig = StorageConfig()


def _load_env_file(env_path: Optional[str]) -> None:
    # Minimal .env loader (no external deps). Only KEY=VALUE per line, '#' comments.
    path = None
    if env_path:
        path = Path(env_path)
    else:
        for candidate in [Path(".env"), Path("bots/linear-bot/.env")]:
            if candidate.exists():
                path = candidate
                break
    if not path or not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        # Do not overwrite pre-set environment variables
        if key and (key not in os.environ):
            os.environ[key] = value


def _parse_assignee_map(raw: Optional[str]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    if not raw:
        return mapping
    # Format: Name1=user1,Name 2=user2
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if "=" not in pair:
            continue
        k, v = pair.split("=", 1)
        k = k.strip()
        v = v.strip().lstrip("@")
        if k:
            mapping[k] = v
    return mapping


def _parse_chats(raw: Optional[str]) -> List[ChatConfig]:
    """Parse CHATS=name1:id1:TEAM1,TEAM2;name2:id2:TEAM3."""
    if not raw:
        return []
    result: List[ChatConfig] = []
    for entry in raw.split(";"):
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split(":")
        if len(parts) < 2:
            continue
        name = parts[0].strip()
        try:
            chat_id = int(parts[1].strip())
        except ValueError:
            continue
        team_keys = []
        if len(parts) >= 3:
            team_keys = [t.strip() for t in parts[2].split(",") if t.strip()]
        result.append(ChatConfig(name=name, chat_id=chat_id, team_keys=team_keys))
    return result


def _parse_allowed_users(raw: Optional[str]) -> List[int]:
    """Parse ALLOWED_USERS=123,456."""
    if not raw:
        return []
    result: List[int] = []
    for item in raw.split(","):
        item = item.strip()
        if item.isdigit():
            result.append(int(item))
    return result


def _parse_user_assignee_map(raw: Optional[str]) -> Dict[int, str]:
    """Parse USER_ASSIGNEE_MAP=123:Name1,456:Name2."""
    if not raw:
        return {}
    result: Dict[int, str] = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if ":" not in pair:
            continue
        k, v = pair.split(":", 1)
        k = k.strip()
        v = v.strip()
        if k.isdigit() and v:
            result[int(k)] = v
    return result


def _parse_team_dm_map(raw: Optional[str]) -> Dict[str, List[int]]:
    """Parse TEAM_DM_MAP=BLUE:123,456;RED:789."""
    if not raw:
        return {}
    result: Dict[str, List[int]] = {}
    for entry in raw.split(";"):
        entry = entry.strip()
        if ":" not in entry:
            continue
        team, users_str = entry.split(":", 1)
        team = team.strip()
        if not team:
            continue
        user_ids: List[int] = []
        for uid in users_str.split(","):
            uid = uid.strip()
            if uid.isdigit():
                user_ids.append(int(uid))
        if user_ids:
            result[team] = user_ids
    return result


def _parse_team_owner_mention(raw: Optional[str]) -> Dict[str, str]:
    """Parse TEAM_OWNER_MENTION=BLUE:@AlexSemenuk,RED:@yurkayurka1."""
    if not raw:
        return {}
    result: Dict[str, str] = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if ":" not in pair:
            continue
        team, mention = pair.split(":", 1)
        team = team.strip()
        mention = mention.strip()
        if team and mention:
            # Ensure @ prefix
            if not mention.startswith("@"):
                mention = f"@{mention}"
            result[team] = mention
    return result


def load_config(path: Optional[str] = None) -> AppConfig:
    # Load .env into environment if present
    _load_env_file(path or os.getenv("LINEAR_BOT_ENV"))

    # Parse multi-chat config
    chats = _parse_chats(os.environ.get("CHATS"))

    # Parse team_keys for backward compat and for LinearConfig
    team_keys_env = os.environ.get("LINEAR_TEAM_KEYS", "").strip()
    team_keys_list = [k.strip() for k in team_keys_env.split(",") if k.strip()]

    # Backward compat: if no CHATS but GROUP_ID exists, create single chat
    legacy_group_id: Optional[int] = None
    if os.environ.get("TELEGRAM_GROUP_ID"):
        legacy_group_id = int(os.environ["TELEGRAM_GROUP_ID"])
        if not chats:
            chats = [
                ChatConfig(
                    name="default",
                    chat_id=legacy_group_id,
                    team_keys=team_keys_list,  # All teams go to this chat
                )
            ]

    telegram = TelegramConfig(
        token=os.environ.get("TELEGRAM_TOKEN", ""),
        group_id=legacy_group_id,
        chats=chats,
        allowed_users=_parse_allowed_users(os.environ.get("ALLOWED_USERS")),
        admin_users=_parse_allowed_users(os.environ.get("ADMIN_USERS")),
        user_assignee_map=_parse_user_assignee_map(os.environ.get("USER_ASSIGNEE_MAP")),
        team_dm_map=_parse_team_dm_map(os.environ.get("TEAM_DM_MAP")),
        team_owner_mention=_parse_team_owner_mention(
            os.environ.get("TEAM_OWNER_MENTION")
        ),
    )

    team_keys = team_keys_list or None

    linear = LinearConfig(
        api_key=os.environ.get("LINEAR_API_KEY", ""),
        team_keys=team_keys,
        include_unstarted=os.environ.get("LINEAR_INCLUDE_UNSTARTED", "").lower()
        in ("true", "1", "yes"),
        assignee_map=_parse_assignee_map(os.environ.get("LINEAR_ASSIGNEE_MAP")),
    )

    schedule = ScheduleConfig(
        timezone=os.environ.get("SCHEDULE_TZ", "UTC"),
        daily_time=os.environ.get("SCHEDULE_DAILY_TIME", "08:00"),
        weekly_cron=os.environ.get("SCHEDULE_WEEKLY_CRON", "0 0 * * MON"),
        poll_interval_seconds=int(os.environ.get("SCHEDULE_POLL_INTERVAL", "60")),
    )

    data_dir = (
        os.environ.get("LINEAR_BOT_DATA")
        or os.environ.get("DATA_DIR")
        or "bots/linear-bot/data"
    )
    storage = StorageConfig(data_dir=data_dir)

    return AppConfig(
        telegram=telegram, linear=linear, schedule=schedule, storage=storage
    )


class JsonStore:
    def __init__(self, base_dir: str):
        self.base_path = Path(base_dir)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.pins_file = self.base_path / "pins.json"
        self.state_file = self.base_path / "state.json"

    def read_json(self, path: Path) -> dict:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text())
        except Exception:
            return {}

    def write_json(self, path: Path, data: dict) -> None:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def get_pins(self) -> dict:
        return self.read_json(self.pins_file)

    def set_pins(self, data: dict) -> None:
        self.write_json(self.pins_file, data)

    def get_state(self) -> dict:
        return self.read_json(self.state_file)

    def set_state(self, data: dict) -> None:
        self.write_json(self.state_file, data)
