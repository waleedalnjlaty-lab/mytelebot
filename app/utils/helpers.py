"""أدوات مساعدة عامة: تطبيع النصوص، الترقيم، التحقق من الصلاحيات."""

from __future__ import annotations

import math
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config import get_settings
import html

def escape_html(text: str) -> str:
    """تخطي رموز HTML لتجنب أخطاء الإرسال في التلغرام"""
    if not text:
        return ""
    return html.escape(str(text))
# تطبيع الحروف العربية الشائعة
_ARABIC_NORMALIZE = str.maketrans(
    {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ة": "ه",
        "ى": "ي",
        "ؤ": "و",
        "ئ": "ي",
    }
)
# إزالة التشكيل (الحركات)
_DIACRITICS = re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed\u06f0]")
_WS = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """توحيد النص للبحث: تنزيل الأحرف، إزالة التشكيل والمسافات الزائدة، تطبيع العربية."""
    text = unicodedata.normalize("NFKC", text or "")
    text = _DIACRITICS.sub("", text)
    text = text.translate(_ARABIC_NORMALIZE)
    text = _WS.sub(" ", text)
    return text.strip().lower()


def build_search_text(*parts: str | None) -> str:
    """دمج عدة حقول في حقل بحث واحد مطبّع."""
    return " ".join(p for p in (normalize_text(x) for x in parts) if p)


def paginate(
    total: int, page: int, per_page: int
) -> tuple[int, int]:
    """إرجاع (current_page, total_pages) مع ضبط حدود الصفحة."""
    total_pages = max(1, math.ceil(total / per_page)) if total else 1
    page = max(0, min(page, total_pages - 1))
    return page, total_pages


def is_admin(user_id: int) -> bool:
    return user_id in get_settings().admin_ids


def format_size(size_bytes: int | None) -> str | None:
    """تحويل البايت إلى نص مقروء مثل 150 MB."""
    if size_bytes is None:
        return None
    value = float(size_bytes)
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}".rstrip(".0").replace(".0 ", " ")
        value /= 1024
    return f"{value:.1f} TB"


def human_time(dt: datetime | None) -> str:
    if dt is None:
        return "-"
    local = dt.astimezone()
    return local.strftime("%Y-%m-%d %H:%M")


def days_ago(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def parse_int(value: str | None, default: int = 0) -> int:
    try:
        return int(value or "")
    except (TypeError, ValueError):
        return default


def sanitize_filename(name: str) -> str:
    """تنظيف اسم ملف قادم من Telegram (منع Path Traversal والأحرف الخطرة)."""
    cleaned = Path(name).name if name else ""
    cleaned = re.sub(r"[\x00-\x1f\x7f]+", "_", cleaned).strip()[:120]
    return cleaned or "file"
