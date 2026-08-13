"""خدمة رفع التطبيق: DevUploads ← ShrinkMe مع حالات تقدم واضحة.

التدفق:
    Telegram file -> DevUploads API (رابط مباشر) -> ShrinkMe API (رابط مختصر)

قواعد النجاح:
    - فشل DevUploads  -> ❌ ولا يُحفظ أي تطبيق.
    - نجاح DevUploads وفشل ShrinkMe -> ⚠️ نحفظ رابط DevUploads فقط ونعلّم المالك.
"""

from __future__ import annotations

import logging
from pathlib import Path

from config import get_settings
from integrations.devupload import DevUploadsClient, build_devupload_client
from integrations.shrankme import ShrankMeClient, build_shrankme_client

logger = logging.getLogger(__name__)


class UploadResult:
    """نتيجة عملية الرفع الكاملة."""

    def __init__(
        self,
        *,
        devupload_url: str | None = None,
        shrankme_url: str | None = None,
        size_bytes: int = 0,
    ) -> None:
        self.devupload_url = devupload_url
        self.shrankme_url = shrankme_url
        self.size_bytes = size_bytes

    @property
    def fully_successful(self) -> bool:
        return bool(self.devupload_url and self.shrankme_url)

    @property
    def partially_successful(self) -> bool:
        return bool(self.devupload_url and not self.shrankme_url)


class UploadService:
    """ينسّق الرفع إلى DevUploads ثم تقصير الرابط عبر ShrinkMe."""

    def __init__(
        self,
        devupload: DevUploadsClient,
        shrankme: ShrankMeClient,
    ) -> None:
        self.devupload = devupload
        self.shrankme = shrankme

    async def run(
        self,
        file_path: Path,
        *,
        filename: str | None = None,
        progress_callback: object | None = None,
    ) -> UploadResult:
        """تنفيذ سلسلة الرفع كاملة. يرفع شذوذًا عند فشل DevUploads.

        progress_callback هو async callable يستقبل نص الحالة، إن وُجد.
        """
        async def _progress(msg: str) -> None:
            if progress_callback is not None:
                cb = progress_callback
                if hasattr(cb, "__call__"):
                    await cb(msg)

        await _progress("⏳ جاري رفع التطبيق إلى Dev Upload...")
        devupload_url = await self.devupload.upload_file(file_path, filename=filename)
        size_bytes = file_path.stat().st_size

        if not devupload_url:
            raise RuntimeError("DevUploads returned an empty URL")

        await _progress("⏳ تم رفع الملف إلى Dev Upload ✅")
        await _progress("⏳ جاري إنشاء رابط التحميل (ShrinkMe)...")

        shrankme_url: str | None = None
        try:
            shrankme_url = await self.shrankme.shorten_url(devupload_url)
        except Exception as exc:
            logger.error("ShrinkMe failed for %s: %s", devupload_url, exc)
            shrankme_url = None

        await _progress("✅ تم تجهيز التطبيق.")

        return UploadResult(
            devupload_url=devupload_url,
            shrankme_url=shrankme_url,
            size_bytes=size_bytes,
        )


async def build_upload_service() -> UploadService:
    settings = get_settings()
    devupload = await build_devupload_client()
    shrankme = await build_shrankme_client()
    return UploadService(devupload=devupload, shrankme=shrankme)
