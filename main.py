import asyncio
import os
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart

import db
import ui
import crm

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = set(map(int, os.getenv("ADMIN_IDS", "").split(",")))
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))

bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


# ================= START =================
@dp.message(CommandStart())
async def start(m: Message):
    await db.upsert_user(m.from_user.id, m.from_user.username, m.from_user.first_name)

    await m.answer(
        ui.main_ui(m.from_user.first_name),
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="💎 Купить")],
                [KeyboardButton(text="📊 Статус")],
                [KeyboardButton(text="🆘 Поддержка")]
            ],
            resize_keyboard=True
        )
    )


# ================= STATUS =================
@dp.message(F.text == "📊 Статус")
async def status(m: Message):
    u = await db.get_user(m.from_user.id)
    exp = u["expire"] if u else 0

    dt = datetime.fromtimestamp(exp).strftime("%d.%m.%Y") if exp else None

    await m.answer(ui.status_ui(dt))


# ================= BUY =================
@dp.message(F.text == "💎 Купить")
async def buy(m: Message):
    await m.answer(
        "💳 Оплата\n💰 500₽\n📸 Отправьте ЧЕК ФОТОМ"
    )


# ================= CHECK PHOTO + ANIMATION =================
@dp.message(F.photo)
async def check(m: Message):
    msg = await m.answer("⏳ Обработка чека...")

    await ui.loading(bot, m.chat.id, msg.message_id)

    for admin in ADMIN_IDS:
        await bot.send_photo(
            admin,
            m.photo[-1].file_id,
            caption=f"💰 CHECK\nID: {m.from_user.id}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton("✅ OK", callback_data=f"ok:{m.from_user.id}"),
                    InlineKeyboardButton("❌ NO", callback_data=f"no:{m.from_user.id}")
                ]
            ])
        )

    await msg.edit_text("📸 Чек отправлен")


# ================= APPROVE =================
@dp.callback_query(F.data.startswith("ok:"))
async def approve(c: CallbackQuery):
    uid = int(c.data.split(":")[1])

    msg = await c.message.edit_text("⚡ Активируем подписку...")

    await ui.loading(bot, c.message.chat.id, msg.message_id)

    now = int(datetime.now().timestamp())
    expire = now + 30 * 86400

    async with db.pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET expire=$1, last_pay=$2 WHERE user_id=$3",
            expire, now, uid
        )

    await bot.send_message(uid, "✅ ПОДПИСКА АКТИВНА")

    await msg.edit_text("✅ APPROVED")


# ================= CRM =================
@dp.message(F.text == "⚙️ Админ")
async def admin(m: Message):
    if m.from_user.id not in ADMIN_IDS:
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("👥 USERS", callback_data="adm:users")]
    ])

    await m.answer("⚙️ ADMIN PANEL", reply_markup=kb)


@dp.callback_query(F.data == "adm:users")
async def users(c: CallbackQuery):
    await crm.users(c)


# ================= RUN =================
async def main():
    await db.init_db()

    crm.register_admins(ADMIN_IDS)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
