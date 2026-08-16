"""سكربت ترحيل صور التطبيقات من Telegram إلى ImgBB.

تشغيل يدوي:
    python scripts/migrate_images.py

أو تلقائياً عند البدء عبر Docker (entrypoint.sh).
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# إضافة المجلد الأب للمسار
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# إن كانت المكتبات غير مثبتة في بايثون الحالي، نعيد التشغيل ببايثون الـ venv المحلي
try:
    import aiogram  # noqa: F401
except ImportError:
    root = Path(__file__).resolve().parent.parent
    candidates = [
        root / "venv" / "Scripts" / "python.exe",
        root / ".venv" / "Scripts" / "python.exe",
        root / "venv" / "bin" / "python",
        root / ".venv" / "bin" / "python",
    ]
    for py in candidates:
        if py.exists():
            os.environ.setdefault("PYTHONIOENCODING", "utf-8")
            os.environ.setdefault("PYTHONUTF8", "1")
            os.execv(str(py), [str(py), *sys.argv])
    print("❌ aiogram غير مثبت. شغّل: pip install -r requirements.txt")
    sys.exit(1)

from aiogram import Bot  # noqa: E402

from app.services.image_migration import migrate_app_images  # noqa: E402
from config import get_settings  # noqa: E402
from database.database import init_db  # noqa: E402

# إعداد السجلات
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """الترحيل الرئيسي: تحميل الصور من Telegram ورفعها إلى ImgBB."""
    settings = get_settings()

    # التحقق من المتطلبات
    if not settings.BOT_TOKEN:
        logger.error("❌ BOT_TOKEN غير موجود!")
        return

    if not settings.IMGBB_API_KEY:
        logger.warning("⚠️ IMGBB_API_KEY غير موجود - تخطي الترحيل")
        return

    logger.info("🚀 بدء ترحيل صور التطبيقات...")

    db = init_db(settings.DATABASE_URL)
    await db.init_models()

    bot = Bot(token=settings.BOT_TOKEN)

    try:
        async with db.session() as session:
            result = await migrate_app_images(bot, session)

        if result.total == 0:
            logger.info("✅ لا توجد صور بحاجة لترحيل")
        else:
            logger.info(
                "📦 المجموع: %d | ✅ نجح: %d | ❌ فشل: %d",
                result.total,
                result.migrated,
                result.failed,
            )
    finally:
        await db.close()
        await bot.session.close()

    logger.info("✨ انتهى الترحيل!")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
