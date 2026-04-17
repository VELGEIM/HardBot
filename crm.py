from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import db

router = Router()


@router.callback_query(F.data == "adm:users")
async def users(c: CallbackQuery):
    rows = await db.fetch("SELECT user_id FROM users LIMIT 20")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=str(r["user_id"]), callback_data=f"user:{r['user_id']}")]
        for r in rows
    ])

    await c.message.edit_text("👥 USERS", reply_markup=kb)
