from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

import db

ADMIN_IDS = {123}

@dp.callback_query(F.data == "adm:users")
async def users(c: CallbackQuery):
    rows = await db.pool.fetch("SELECT user_id FROM users LIMIT 20")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=str(r["user_id"]), callback_data=f"user:{r['user_id']}")]
        for r in rows
    ])

    await c.message.edit_text("👥 USERS", reply_markup=kb)
