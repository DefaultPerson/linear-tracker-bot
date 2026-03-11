from aiogram import Dispatcher
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from ..reports import send_current_report
from ..utils.group_guard import only_group


def register_reports(dp: Dispatcher, config) -> None:
    @dp.message(Command("ct"))
    @only_group(config)
    async def current_report(message: Message, command: CommandObject):
        await send_current_report(
            message.bot,
            message.chat.id,
            config,
            pin=False,
            reply_to_message_id=message.message_id,
        )
