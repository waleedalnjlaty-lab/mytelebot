"""أدوات مساعدة للتفاعل مع Telegram (تنزيل ملفات، معالجة أخطاء، مهلة الإرسال)."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

import aiofiles
import httpx
from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
    TelegramUnauthorizedError,
)

logger = logging.getLogger(__name__)

# مهلة تنزيل الملفات الكبيرة: 10 دقائق للقراءة (مطلوبة للملفات حتى 2GB)
DOWNLOAD_TIMEOUT = httpx.Timeout(
    timeout=600.0,
    connect=30.0,
    read=600.0,
    write=600.0,
    pool=30.0,
)
_DOWNLOAD_CHUNK = 64 * 1024  # 64KB


async def download_telegram_file(
    bot: Bot, file_id: str, destination: str | Path
) -> Path:
    """تنزيل ملف من Telegram مباشرةً إلى القرص (تدفقي عبر httpx، دون RAM).

    محمي بمهلة قراءة 10 دقائق؛ وعند أي فشل (TimeoutError أو غيره) يُحذف
    الملف الجزئي الناتج حتى لا يتراكم شظايا مكسورة في مجلد tmp.
    """
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)

    file = await bot.get_file(file_id)
    url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"

    try:
        async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                async with aiofiles.open(destination, "wb") as out:
                    async for chunk in response.aiter_bytes(_DOWNLOAD_CHUNK):
                        await out.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return destination


async def send_with_retry(
    bot: Bot,
    *,
    chat_id: int | str,
    text: str | None = None,
    parse_mode: str | None = "HTML",
    reply_markup: Any = None,
    photo: str | None = None,
    disable_web_page_preview: bool = True,
    max_attempts: int = 3,
    **kwargs: Any,
) -> bool:
    """إرسال رسالة مع معالجة صحيحة لـ FloodWait و أخطاء الحظر.

    يعيد True عند النجاح، False عند فشل نهائي (مثل توقف المستخدم عن البوت).
    أخطاء المهلة (Timeout) تعامل كأخطاء شبكة مؤقتة وتُعاد المحاولة.
    """
    for attempt in range(1, max_attempts + 1):
        try:
            if photo:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=photo,
                    caption=text,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup,
                    **kwargs,
                )
            else:
                await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup,
                    disable_web_page_preview=disable_web_page_preview,
                    **kwargs,
                )
            return True
        except TelegramRetryAfter as exc:
            if attempt < max_attempts:
                logger.info("FloodWait %ss for chat %s", exc.retry_after, chat_id)
                await _sleep_safe(exc.retry_after)
                continue
            return False
        except (TelegramForbiddenError, TelegramBadRequest) as exc:
            # المستخدم حظر البوت، أو chat غير صالح — لا فائدة من إعادة المحاولة
            logger.debug("Cannot send to chat %s: %s", chat_id, exc)
            return False
        except TelegramUnauthorizedError:
            logger.error("Bot token is invalid!")
            return False
        except (TimeoutError, httpx.TimeoutException) as exc:
            logger.warning("Timeout sending to chat %s: %s", chat_id, exc)
            if attempt < max_attempts:
                await _sleep_safe(attempt * 2)
                continue
            return False
        except TelegramAPIError as exc:
            logger.warning("Telegram API error for chat %s: %s", chat_id, exc)
            if attempt < max_attempts:
                await _sleep_safe(attempt * 2)
                continue
            return False
    return False


async def _sleep_safe(seconds: float) -> None:
    await asyncio.sleep(max(0.1, min(seconds, 60)))
