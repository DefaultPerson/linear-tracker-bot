import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from .config import load_config
from .handlers import register_handlers
from .scheduler import setup_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("linear-bot")


async def run() -> None:
    config = load_config()
    bot = Bot(
        token=config.telegram.token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    register_handlers(dp, config)
    await setup_scheduler(bot, dp, config)

    logger.info("Starting bot polling...")
    await dp.start_polling(bot)


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
if __name__ == "__main__":
    main()
