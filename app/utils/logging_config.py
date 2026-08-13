"""إعداد التسجيل (Logging) — بدون أي بيانات حساسة في المخرجات."""

from __future__ import annotations

import logging
import sys

_CONFIGURED = False


def setup_logging(level: int = logging.INFO) -> None:
    """تهيئة logging مرة واحدة. لا نطبع أبدًا مفاتيح API أو توكنات."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)

    # خفض ضجيج المكتبات
    for noisy in ("aiogram", "httpx", "sqlalchemy"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True
