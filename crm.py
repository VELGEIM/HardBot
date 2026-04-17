from aiogram import F, Router
from aiogram.types import CallbackQuery
import db
import ui
from config import ADMIN_IDS

router = Router()


@router.callback_query(F.data == "adm:users")
async def users(c: CallbackQuery):
    rows = await db.pool.fetch("SELECT user_id FROM users LIMIT 20")

    kb = []
    text = "👥 USERS LIST\n\n"

    for r in rows:
        uid = r["user_id"]
        text += f"{uid}\n"
        kb.append([InlineKeyboardButton(text=str(uid), callback_data=f"user:{uid}")])

    await c.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))


@router.callback_query(F.data.startswith("ban:"))
async def ban(c: CallbackQuery):
    uid = int(c.data.split(":")[1])

    await db.execute("UPDATE users SET is_banned=1 WHERE user_id=$1", uid)
    await c.answer("BANNED")
