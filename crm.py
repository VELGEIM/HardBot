from aiogram import Router, F
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


@router.callback_query(F.data.startswith("ban:"))
async def ban(c: CallbackQuery):
    uid = int(c.data.split(":")[1])
    await db.execute("UPDATE users SET is_banned=1 WHERE user_id=$1", uid)
    await c.answer("BANNED")


@router.callback_query(F.data.startswith("unban:"))
async def unban(c: CallbackQuery):
    uid = int(c.data.split(":")[1])
    await db.execute("UPDATE users SET is_banned=0 WHERE user_id=$1", uid)
    await c.answer("UNBANNED")
