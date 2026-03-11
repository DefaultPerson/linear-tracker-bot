from aiogram import Dispatcher
from .commands import setup_commands

from .start import register_start
from .reports import register_reports
from .personal import register_personal


def register_handlers(dp: Dispatcher, config) -> None:
    setup_commands(dp, config)
    register_start(dp, config)
    register_reports(dp, config)
    register_personal(dp, config)
