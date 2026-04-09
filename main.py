import asyncio
import aiosqlite
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode

import os

# ================== CONFIG ==================
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

bot = Bot(token=TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

DB = "bot.db"


# ================== DB ==================
async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            expire DATETIME
        )
        """)
        await db.commit()


async def set_subscription(user_id: int, days: int = 30):
    expire = datetime.now() + timedelta(days=days)

    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        INSERT INTO users (user_id, expire)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET expire=excluded.expire
        """, (user_id, expire))
        await db.commit()


async def get_subscription(user_id: int):
    async with aiosqlite.connect(DB) as db:
        async with db.execute("SELECT expire FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            if not row:
                return None
            return datetime.fromisoformat(row[0])


async def is_active(user_id: int):
    expire = await get_subscription(user_id)
    if not expire:
        return False
    return expire > datetime.now()


# ================== UI ==================
def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔥 Купить подписку", callback_data="buy")],
        [InlineKeyboardButton(text="⏳ Продлить", callback_data="extend")],
        [InlineKeyboardButton(text="📦 Мой статус", callback_data="status")]
    ])


def admin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Дать подписку", callback_data="admin_add")],
        [InlineKeyboardButton(text="📊 Пользователи", callback_data="admin_users")]
    ])


# ================== START ==================
@dp.message(CommandStart())
async def start(message: Message):
    active = await is_active(message.from_user.id)

    if not active:
        await message.answer(
            "❌ У тебя нет активной подписки\n\nКупи доступ ниже 👇",
            reply_markup=main_menu()
        )
        return

    await message.answer(
        "✅ Добро пожаловать!\nТы в системе.",
        reply_markup=main_menu()
    )


# ================== BLOCK SYSTEM ==================
async def check_access(user_id: int):
    if user_id == ADMIN_ID:
        return True
    return await is_active(user_id)


def access_denied():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔥 Купить доступ", callback_data="buy")]
    ])


# ================== CALLBACKS ==================
@dp.callback_query(F.data == "buy")
async def buy(call: CallbackQuery):
    await call.message.edit_text(
        "💎 Подписка:\n\n"
        "• 30 дней доступа\n"
        "• Полный функционал\n\n"
        "💰 Цена: 10€\n\n"
        "После оплаты нажми 'Продлить'",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Я оплатил", callback_data="paid")]
        ])
    )


@dp.callback_query(F.data == "extend")
async def extend(call: CallbackQuery):
    await call.message.edit_text(
        "⏳ Продление подписки:\n\n"
        "Нажми кнопку после оплаты 👇",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✔ Продлить на 30 дней", callback_data="paid")]
        ])
    )


@dp.callback_query(F.data == "paid")
async def paid(call: CallbackQuery):
    await set_subscription(call.from_user.id, 30)

    await call.message.edit_text(
        "✅ Оплата подтверждена!\nПодписка активна на 30 дней 🔥"
    )


@dp.callback_query(F.data == "status")
async def status(call: CallbackQuery):
    expire = await get_subscription(call.from_user.id)

    if not expire:
        text = "❌ Подписки нет"
    else:
        text = f"📅 Действует до: {expire.strftime('%Y-%m-%d %H:%M')}"

    await call.message.edit_text(text, reply_markup=main_menu())


# ================== ADMIN ==================
@dp.message(F.text == "/admin")
async def admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("⚙ Админ панель", reply_markup=admin_menu())


# ================== PROTECTED CONTENT EXAMPLE ==================
@dp.message(F.text == "content")
async def content(message: Message):
    if not await check_access(message.from_user.id):
        await message.answer("⛔ Нет доступа", reply_markup=access_denied())
        return

    await message.answer("🔥 Секретный контент открыт!")


# ================== REMINDER SYSTEM ==================
async def reminder_loop():
    while True:
        async with aiosqlite.connect(DB) as db:
            async with db.execute("SELECT user_id, expire FROM users") as cur:
                rows = await cur.fetchall()

                for user_id, expire in rows:
                    try:
                        exp = datetime.fromisoformat(expire)
                        days_left = (exp - datetime.now()).days

                        if days_left == 3:
                            await bot.send_message(
                                user_id,
                                "⚠️ Подписка закончится через 3 дня!"
                            )

                    except:
                        pass

        await asyncio.sleep(3600)  # каждый час


# ================== MAIN ==================
async def main():
    await init_db()
    asyncio.create_task(reminder_loop())

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
