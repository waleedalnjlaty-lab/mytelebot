"""خدمة الإعلانات الجماعية مع معالجة صحيحة لـ FloodWait."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)

logger = logging.getLogger(__name__)

BROADCAST_SLEEP = 0.05  # 20 رسالة/ثانية كحد أقصى لتفادي 429
BROADCAST_LIMIT_PER_SEC = 20


class BroadcastStats:
    def __init__(self) -> None:
        self.sent = 0
        self.failed = 0

    def __str__(self) -> str:
        return (
            "📊 نتائج الإرسال:\n"
            f"✅ تم الإرسال: {self.sent}\n"
            f"❌ فشل: {self.failed}"
        )


async def broadcast_to_users(
    bot: Bot,
    user_ids: list[int],
    *,
    text: str,
    parse_mode: str = "HTML",
    chunk_size: int = 50,
) -> BroadcastStats:
    """إرسال رسالة لمجموعة مستخدمين مع الالتزام بحدود Telegram."""
    stats = BroadcastStats()
    for i in range(0, len(user_ids), chunk_size):
        chunk = user_ids[i : i + chunk_size]
        for user_id in chunk:
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=text,
                    parse_mode=parse_mode,
                    disable_web_page_preview=True,
                )
                stats.sent += 1
            except TelegramRetryAfter as exc:
                logger.info("FloodWait %ss before continuing broadcast", exc.retry_after)
                await asyncio.sleep(min(exc.retry_after, 60))
            except (TelegramForbiddenError, TelegramBadRequest):
                stats.failed += 1
            except Exception as exc:  # شبكة أو أخطاء مؤقتة
                logger.warning("Broadcast error to %s: %s", user_id, exc)
                stats.failed += 1
        await asyncio.sleep(BROADCAST_SLEEP * chunk_size)
    return stats


async def broadcast_to_chat(bot: Bot, chat_id: int, *, text: str) -> bool:
    """إرسال رسالة إلى مجموعة أو قناة واحدة."""
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        return True
    except TelegramRetryAfter as exc:
        await asyncio.sleep(min(exc.retry_after, 60))
        return await broadcast_to_chat(bot, chat_id, text=text)
    except Exception as exc:
        logger.warning("Broadcast to chat %s failed: %s", chat_id, exc)
        return False
