from aiogram import F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

import db


def menu(uid):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💎 Store")],
            [KeyboardButton(text="📊 Profile")]
        ],
        resize_keyboard=True
    )


@dp.message(F.text == "/start")
async def start(m: Message):
    await db.exec(
        "INSERT INTO users(user_id) VALUES($1) ON CONFLICT DO NOTHING",
        m.from_user.id
    )

    await m.answer("🔥 HARDHUB PRO", reply_markup=menu(m.from_user.id))


@dp.message(F.text == "📊 Profile")
async def profile(m: Message):
    u = await db.fetch_user(m.from_user.id)

    if u and u["expire"] > 0:
        await m.answer("🟢 ACTIVE SUB")
    else:
        await m.answer("🔴 NO SUB")
