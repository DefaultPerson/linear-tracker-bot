from aiogram import Dispatcher
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from ..reports import send_current_report
from ..utils.group_guard import only_group


def register_reports(dp: Dispatcher, config) -> None:
    @dp.message(Command("ct"))
    @only_group(config)
    async def current_report(message: Message, command: CommandObject):
        # Respect the chat's team_keys so /ct mirrors the scheduled per-chat
        # report; fall back to global keys for unconfigured chats/DMs.
        chat_cfg = next(
            (c for c in config.telegram.chats if c.chat_id == message.chat.id), None
        )
        await send_current_report(
            message.bot,
            message.chat.id,
            config,
            pin=False,
            reply_to_message_id=message.message_id,
            team_keys_filter=chat_cfg.team_keys
            if chat_cfg and chat_cfg.team_keys
            else None,
            thread_id=message.message_thread_id,
        )
