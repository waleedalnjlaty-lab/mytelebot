#!/bin/sh
# نقطة الدخول لـ Docker - تشغيل الترحيل أولاً ثم البوت

set -e

echo "🚀 بدء تشغيل Waleed Zone Bot..."

# تشغيل سكربت الترحيل (يتخطى إذا لم تكن هناك صور)
echo "📦 فحص ترحيل الصور..."
python scripts/migrate_images.py || true

# تشغيل البوت الرئيسي
echo "🤖 تشغيل البوت..."
exec python -u main.py
