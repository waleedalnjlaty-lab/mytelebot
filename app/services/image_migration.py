"""خدمة ترحيل صور التطبيقات من Telegram إلى ImgBB.

تُستخدم من:
    - سكربت CLI:  python scripts/migrate_images.py
    - زر مخصص في لوحة الإدارة داخل البوت.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from database.models import Application
from integrations.imgbb import ImgBBUploader

logger = logging.getLogger(__name__)


@dataclass
class MigrationResult:
    total: int = 0
    migrated: int = 0
    failed: int = 0


async def migrate_app_images(
    bot: Bot,
    session: AsyncSession,
    uploader: ImgBBUploader | None = None,
) -> MigrationResult:
    """يرحّل صور التطبيقات من Telegram إلى ImgBB ويربطها بـ image_url.

    يعالج التطبيقات التي لديها `icon_file_id` لكن بدون `image_url`.
    يحفظ التغييرات تلقائيًا في نهاية العملية.
    """
    settings = get_settings()
    if uploader is None:
        if not settings.IMGBB_API_KEY:
            raise RuntimeError("IMGBB_API_KEY غير موجود في ملف .env")
        uploader = ImgBBUploader(api_key=settings.IMGBB_API_KEY)

    query = select(Application).where(
        (Application.icon_file_id.isnot(None))
        & ((Application.image_url.is_(None)) | (Application.image_url == ""))
    )
    result = await session.execute(query)
    apps = result.scalars().all()

    summary = MigrationResult(total=len(apps))
    if not apps:
        return summary

    logger.info("📦 وجدنا %d تطبيق بحاجة لترحيل الصور", len(apps))
    for idx, app in enumerate(apps, 1):
        if not app.icon_file_id:
            continue
        logger.info("[%d/%d] جاري رفع صورة: %s", idx, len(apps), app.name)
        try:
            image_url = await uploader.upload_telegram_photo(bot, app.icon_file_id)
        except Exception as exc:
            logger.error("❌ خطأ في %s: %s", app.name, exc)
            summary.failed += 1
            continue

        if image_url:
            app.image_url = image_url
            summary.migrated += 1
            logger.info("✅ نجح: %s...", image_url[:60])
        else:
            summary.failed += 1
            logger.warning("⚠️ فشل رفع صورة %s", app.name)

    await session.commit()
    logger.info("💾 تم حفظ %d صورة", summary.migrated)
    return summary
