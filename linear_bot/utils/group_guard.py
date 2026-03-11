import functools
import logging
from aiogram.types import Message

logger = logging.getLogger(__name__)


def only_group(config):
    """Allow command ONLY in configured group chats. Ignore private chats."""

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(message: Message, *args, **kwargs):
            chat_type = message.chat.type
            chat_id = message.chat.id

            # Only allow group/supergroup - ignore private and channels
            if chat_type not in {"group", "supergroup"}:
                return

            # Check if chat is in configured list
            allowed_ids = {c.chat_id for c in config.telegram.chats}
            if config.telegram.group_id:
                allowed_ids.add(config.telegram.group_id)

            # If no chats configured, allow all groups; otherwise check whitelist
            if not allowed_ids or chat_id in allowed_ids:
                return await func(message, *args, **kwargs)

            logger.debug(f"Chat {chat_id} not in allowed chats, ignoring")
            return

        return wrapper

    return decorator
