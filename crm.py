from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import db

ADMIN_IDS = set()


def register_admins(ids):
    global ADMIN_IDS
    ADMIN_IDS = ids


async def users(call: CallbackQuery):
    rows = await db.pool.fetch("SELECT user_id FROM users LIMIT 25")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=str(r["user_id"]), callback_data=f"user:{r['user_id']}")]
        for r in rows
    ])

    await call.message.edit_text("👥 CRM USERS", reply_markup=kb)
