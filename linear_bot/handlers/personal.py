from aiogram import Dispatcher
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from ..reports import send_personal_tasks
from ..utils.group_guard import only_group


def register_personal(dp: Dispatcher, config) -> None:
    @dp.message(Command("mt"))
    @only_group(config)
    async def personal(message: Message, command: CommandObject):
        user = message.from_user
        await send_personal_tasks(
            message.bot,
            message.chat.id,
            user,
            config,
            reply_to_message_id=message.message_id,
        )
