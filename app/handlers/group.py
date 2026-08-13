"""معالجات المجموعة: الترحيب، الحماية/Anti-Spam، وأوامر الإشراف للمشرفين."""

from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import ChatMemberUpdated, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.group_service import GroupService
from app.utils.helpers import is_admin

logger = logging.getLogger(__name__)

router = Router(name="group")

group_service = GroupService()

MODERATION_COMMANDS = {"ban", "unban", "mute", "unmute", "warn", "del", "pin", "warns", "promote", "demote", "lock", "unlock", "id", "commands"}

# خريطة الكلمات العربية المباشرة للرد السريع
ARABIC_MOD_KEYWORDS = {
    "حذف": "del",
    "مسح": "del",
    "حظر": "ban",
    "طرد": "ban",
    "كتم": "mute",
    "فك الحظر": "unban",
    "فك الكتم": "unmute",
    "تثبيت": "pin",
    "ترفيع": "promote",
    "تنزيل": "demote",
    "قفل": "lock",
    "فتح": "unlock",
    "آيدي": "id",
    "الأوامر": "commands",
    "الاوامر": "commands",
}


async def _can_moderate(
    bot: Bot, message: Message, session: AsyncSession
) -> bool:
    """السماح بالتحكم للمالك فقط أو لمشرفي المجموعة."""
    sender = message.from_user
    if sender is None:
        return False
    if is_admin(sender.id):
        return True
    try:
        member = await bot.get_chat_member(message.chat.id, sender.id)
        return member.status in {"administrator", "creator"}
    except Exception:
        return False


async def _execute_moderation(
    message: Message, session: AsyncSession, action: str
) -> None:
    bot = message.bot
    # حماية البوت من الأوامر الذاتية أو من البوتات
    if message.from_user is None or message.from_user.is_bot:
        return
    if not await _can_moderate(bot, message, session):
        await message.answer("⛔ هذه الصلاحية للمشرفين فقط.")
        return

    if action == "del":
        await group_service.delete_message(bot, message)
        return
    elif action == "lock":
        result = await group_service.lock_chat(bot, message)
    elif action == "unlock":
        result = await group_service.unlock_chat(bot, message)
    elif action == "id":
        result = await group_service.get_user_id(message)
    elif action == "commands":
        result = (
            "🛠 **قائمة أوامر الإشراف والحماية**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🛡 **أوامر المشرفين (بالأوامر أو بالرد بكلمة):**\n"
            "• `حذف` / `مسح` ⟵ لحذف الرسالة المستهدفة\n"
            "• `حظر` / `طرد` ⟵ حظر العضو من المجموعة\n"
            "• `فك الحظر` ⟵ إلغاء حظر العضو\n"
            "• `كتم` ⟵ منع العضو من إرسال الرسائل\n"
            "• `فك الكتم` ⟵ السماح للعضو بالتكلم\n"
            "• `ترفيع` ⟵ ترقية العضو إلى مشرف\n"
            "• `تنزيل` ⟵ إزالة الصلاحيات عن المشرف\n"
            "• `تثبيت` ⟵ تثبيت رسالة في المجموعة\n"
            "• `قفل` / `فتح` ⟵ قفل أو فتح الدردشة\n"
            "• `آيدي` ⟵ عرض معلومات المستخدم\n\n"
            "📋 **الأوامر النصية المباشرة:**\n"
            "• `/admins` ⟵ عرض قائمة مشرفي المجموعة\n"
            "• `/warns` ⟵ عرض عدد التحذيرات"
        )
    elif action == "ban":
        result = await group_service.ban_member(bot, session, message)
    elif action == "unban":
        result = await group_service.unban_member(bot, session, message)
    elif action == "mute":
        result = await group_service.mute_member(bot, session, message)
    elif action == "unmute":
        result = await group_service.unmute_member(bot, session, message)
    elif action == "promote":
        result = await group_service.promote_member(bot, session, message)
    elif action == "demote":
        result = await group_service.demote_member(bot, session, message)
    elif action == "warn":
        target = message.reply_to_message
        if target is None or target.from_user is None:
            await message.answer("⚠️ قم بالرد على رسالة العضو لتحذيره.")
            return
        if target.from_user.is_bot:
            await message.answer("❌ لا يمكنك تحذير البوتات!")
            return
        result = await group_service.warn(
            bot, session, message, target=target, reason="تحذير من مشرف"
        )
    elif action == "pin":
        result = await group_service.pin_message(bot, message)
    elif action == "warns":
        result = await group_service.show_warnings(bot, session, message)
    else:
        return

    if result is not None:
        await message.answer(result)


def make_moderation_handler(action: str):
    async def handler(message: Message, session: AsyncSession) -> None:
        await _execute_moderation(message, session, action)
    return handler


for cmd in MODERATION_COMMANDS:
    router.message.register(make_moderation_handler(cmd), Command(cmd))


@router.message(Command("admins"))
async def on_admins(message: Message) -> None:
    try:
        admins = await message.bot.get_chat_administrators(message.chat.id)
    except Exception as exc:
        logger.debug("get_chat_administrators failed: %s", exc)
        await message.reply("❌ تعذر جلب قائمة المشرفين.")
        return
    lines = ["📋 **قائمة مشرفي المجموعة:**", "━━━━━━━━━━━━"]
    for admin in admins:
        user = admin.user
        name = f"@{user.username}" if user.username else user.full_name
        tag = "👑 مالك المجموعة" if admin.status == "creator" else "🛡 مشرف"
        lines.append(f"{tag}: {name}")
    await message.reply("\n".join(lines))


@router.chat_member()
async def on_member_joined(
    event: ChatMemberUpdated, session: AsyncSession
) -> None:
    """الترحيب بالعضو الجديد (إن كان مفعّلًا)."""
    await group_service.welcome_if_needed(event.bot, session, event)

@router.message(F.chat.type.in_(["group", "supergroup"]))
async def on_group_message(
    message: Message, session: AsyncSession
) -> None:
    """معالج شامل: يفحص أوامر الإشراف العربية أولاً، وإذا لم تكن أمراً يفحص الرسالة بنظام الحماية."""
    if message.from_user is None or message.from_user.is_bot:
        return

    is_cmd_executed = False

    if message.text:
        text = message.text.strip().lower()
        parts = text.split()
        
        action = None
        target_index = 1
        
        # 1. فحص هل أول كلام المشرف هو أمر؟ (مثل: فك الحظر، كتم)
        if len(parts) > 1 and f"{parts[0]} {parts[1]}" in ARABIC_MOD_KEYWORDS:
            action = ARABIC_MOD_KEYWORDS[f"{parts[0]} {parts[1]}"]
            target_index = 2
        elif parts and parts[0] in ARABIC_MOD_KEYWORDS:
            action = ARABIC_MOD_KEYWORDS[parts[0]]
            target_index = 1
            
        # 2. فحص هل آخر كلام المشرف هو أمر؟ (مثل: هذا الشخص مزعج تنزيل)
        if not action and parts:
            if parts[-1] in ARABIC_MOD_KEYWORDS:
                action = ARABIC_MOD_KEYWORDS[parts[-1]]
            elif len(parts) > 1 and f"{parts[-2]} {parts[-1]}" in ARABIC_MOD_KEYWORDS:
                action = ARABIC_MOD_KEYWORDS[f"{parts[-2]} {parts[-1]}"]

        # إذا تم التقاط أمر مشرف
        if action:
            if await _can_moderate(message.bot, message, session):
                is_cmd_executed = True
                
                target_user = None
                if message.reply_to_message and message.reply_to_message.from_user:
                    target_user = message.reply_to_message.from_user

                # تجهيز النص الجديد
                new_text = message.text
                if target_user and action in {"ban", "unban", "mute", "unmute", "promote", "demote", "warn"}:
                    identifier = f"@{target_user.username}" if target_user.username else str(target_user.id)
                    new_text = f"/{action} {identifier}"
                elif len(parts) > target_index and action in {"ban", "unban", "mute", "unmute", "promote", "demote", "warn"}:
                    target_identifier = parts[target_index]
                    new_text = f"/{action} {target_identifier}"
                else:
                    if not message.text.startswith("/"):
                        new_text = f"/{action}"

                # الحل السحري: إنشاء نسخة جديدة من الرسالة مع النص المُعدّل لتجاوز تجميد البيانات
                modified_message = message.model_copy(update={"text": new_text})

                await _execute_moderation(modified_message, session, action)

    # 3. إذا لم يقم المشرف بتنفيذ أمر، قم بتشغيل فحص الحماية العادي (Anti-Spam)
    if not is_cmd_executed:
        await group_service.check_message(message.bot, session, message)