import asyncio
import aiosqlite
import os
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ChatJoinRequest
)
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup


# ================= CONFIG =================
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
CARD = "1234 5678 9012 3456"

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()
DB = "bot.db"


# ================= FSM =================
class PayState(StatesGroup):
    wait_screenshot = State()


# ================= DB =================
async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            expire INTEGER
        )
        """)
        await db.commit()


async def set_user(user_id: int, days: int = 30):
    expire = int((datetime.now() + timedelta(days=days)).timestamp())

    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        INSERT OR REPLACE INTO users VALUES (?, ?)
        """, (user_id, expire))
        await db.commit()


async def is_active(user_id: int):
    async with aiosqlite.connect(DB) as db:
        async with db.execute("SELECT expire FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()

    if not row:
        return False

    return int(row[0]) > int(datetime.now().timestamp())


# ================= UI =================
def menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Купить 500₽", callback_data="buy")],
        [InlineKeyboardButton(text="📊 Статус", callback_data="status")]
    ])


def paid_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 Я оплатил", callback_data="paid")]
    ])


def admin_kb(user_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"ok:{user_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"no:{user_id}")
        ]
    ])


# ================= START =================
@dp.message(CommandStart())
async def start(message: Message):
    if not await is_active(message.from_user.id) and message.from_user.id != ADMIN_ID:
        await message.answer("❌ Доступ закрыт\nКупи подписку 👇", reply_markup=menu())
        return

    await message.answer("🔥 Добро пожаловать", reply_markup=menu())


# ================= BUY =================
@dp.callback_query(F.data == "buy")
async def buy(call: CallbackQuery, state: FSMContext):
    await state.set_state(PayState.wait_screenshot)

    await call.message.answer(
        f"💳 Переведи 500₽ на карту:\n\n<b>{CARD}</b>\n\n"
        "После оплаты нажми кнопку 👇",
        reply_markup=paid_kb()
    )


@dp.callback_query(F.data == "paid")
async def paid(call: CallbackQuery):
    await call.message.answer("📸 Отправь скрин оплаты")


# ================= SCREENSHOT =================
@dp.message(PayState.wait_screenshot, F.photo)
async def screenshot(message: Message, state: FSMContext):
    photo = message.photo[-1].file_id

    await bot.send_photo(
        ADMIN_ID,
        photo,
        caption=f"💰 Оплата\nUser: {message.from_user.id}",
        reply_markup=admin_kb(message.from_user.id)
    )

    await message.answer("⏳ Ожидай подтверждения")
    await state.clear()


# ================= APPROVE =================
@dp.callback_query(F.data.startswith("ok:"))
async def approve(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return

    user_id = int(call.data.split(":")[1])

    await set_user(user_id, 30)

    try:
        await bot.approve_chat_join_request(CHANNEL_ID, user_id)
    except:
        pass

    await bot.send_message(user_id, "✅ Доступ выдан на 30 дней")
    await call.message.edit_text("OK")


# ================= JOIN REQUEST =================
@dp.chat_join_request()
async def join(request: ChatJoinRequest):
    if await is_active(request.from_user.id):
        await request.approve()
    else:
        await request.decline()


# ================= STATUS =================
@dp.callback_query(F.data == "status")
async def status(call: CallbackQuery):
    async with aiosqlite.connect(DB) as db:
        async with db.execute("SELECT expire FROM users WHERE user_id=?", (call.from_user.id,)) as cur:
            row = await cur.fetchone()

    if not row:
        await call.message.answer("❌ Нет подписки")
        return

    exp = datetime.fromtimestamp(row[0])

    await call.message.answer(f"📅 До: {exp}")


# ================= AUTO CHECK =================
async def cleanup():
    while True:
        now = int(datetime.now().timestamp())

        async with aiosqlite.connect(DB) as db:
            async with db.execute("SELECT user_id, expire FROM users") as cur:
                rows = await cur.fetchall()

                for user_id, exp in rows:
                    if exp < now:
                        try:
                            await bot.ban_chat_member(CHANNEL_ID, user_id)
                            await bot.unban_chat_member(CHANNEL_ID, user_id)
                        except:
                            pass

                        await db.execute("DELETE FROM users WHERE user_id=?", (user_id,))

                await db.commit()

        await asyncio.sleep(3600)


# ================= MAIN =================
async def main():
    await init_db()
    asyncio.create_task(cleanup())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
