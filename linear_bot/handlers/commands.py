from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, BotCommandScopeChat


def setup_commands(dp: Dispatcher, config) -> None:
    async def _set_commands_scoped(bot: Bot) -> None:
        commands = [
            BotCommand(command="start", description="Show help and command list"),
            BotCommand(command="ct", description="Current report"),
            BotCommand(command="mt", description="Personal tasks"),
        ]
        if config.telegram.group_id:
            scope = BotCommandScopeChat(chat_id=config.telegram.group_id)
            await bot.set_my_commands(commands, scope=scope)
            # Clear global commands to avoid showing outside the configured group
            await bot.set_my_commands([])
        else:
            await bot.set_my_commands(commands)

    dp.startup.register(_set_commands_scoped)


async def _set_commands(bot: Bot) -> None:
    # Kept for backward compatibility; no-op
    return
