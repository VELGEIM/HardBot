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
import security
import crm

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = set(map(int, os.getenv("ADMIN_IDS","").split(",")))
CARD = os.getenv("CARD_NUMBER","0000")

bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


# ================= START =================
@dp.message(CommandStart())
async def start(m: Message):
    await db.upsert_user(m.from_user.id, m.from_user.username, m.from_user.first_name)

    await m.answer(
        ui.main_menu(m.from_user.first_name),
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
    await m.answer(ui.status_text(u["expire"] if u else 0))


# ================= BUY =================
@dp.message(F.text == "💎 Купить")
async def buy(m: Message):
    await m.answer(
        ui.pay_text(500, CARD),
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="⬅️ Отмена")]],
            resize_keyboard=True
        )
    )


# ================= CHECK PHOTO SYSTEM =================
@dp.message(F.photo)
async def photo_check(m: Message):
    for admin in ADMIN_IDS:
        await bot.send_photo(
            admin,
            m.photo[-1].file_id,
            caption=f"💰 NEW CHECK\nID: {m.from_user.id}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton("✅ APPROVE", callback_data=f"ok:{m.from_user.id}"),
                    InlineKeyboardButton("❌ REJECT", callback_data=f"no:{m.from_user.id}")
                ]
            ])
        )

    await m.answer("📸 Чек отправлен на проверку")


# ================= ADMIN APPROVE =================
@dp.callback_query(F.data.startswith("ok:"))
async def approve(c: CallbackQuery):
    uid = int(c.data.split(":")[1])

    now = int(datetime.now().timestamp())
    expire = now + 30 * 86400

    async with db.pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET expire=$1, last_pay=$2 WHERE user_id=$3",
            expire, now, uid
        )

    await bot.send_message(uid, "✅ ПОДПИСКА АКТИВИРОВАНА")

    await c.message.edit_caption("✅ APPROVED")


# ================= SUPPORT =================
@dp.message(F.text == "🆘 Поддержка")
async def support(m: Message):
    await m.answer("📞 Напишите вопрос — ответ придёт от админа")


# ================= ADMIN =================
@dp.message(F.text == "⚙️ Админ")
async def admin(m: Message):
    if m.from_user.id not in ADMIN_IDS:
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 USERS", callback_data="adm:users")]
    ])

    await m.answer("⚙️ ADMIN PANEL", reply_markup=kb)


# ================= CRM =================
@dp.callback_query(F.data == "adm:users")
async def users(c: CallbackQuery):
    await crm.users_list(c)


# ================= MAIN =================
async def main():
    await db.init_db()

    crm.register_admins(ADMIN_IDS)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
