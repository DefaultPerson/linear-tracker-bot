from aiogram import Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

from ..utils.group_guard import only_group


def register_start(dp: Dispatcher, config) -> None:
    @dp.message(Command("start"))
    @only_group(config)
    async def start(message: Message):
        text = (
            "<b>Linear Bot</b>\n\n"
            "/start - Show help and command list\n"
            "/ct - Current report\n"
            "/mt - Personal tasks (user-specific)\n\n"
            "#linear"
        )
        await message.answer(text, reply_to_message_id=message.message_id)
