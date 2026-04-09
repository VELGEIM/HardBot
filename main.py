import asyncio
import logging
import os
import aiosqlite

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command

# =====================
# ENV
# =====================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

DB_PATH = "bot.db"

# =====================
# LOGGING
# =====================
logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# =====================
# DB INIT
# =====================
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            expire INTEGER
        )
        """)
        await db.commit()

# =====================
# CHECK SUB
# =====================
async def is_active(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT expire FROM users WHERE id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            if not row:
                return False
            return row[0] > int(asyncio.get_event_loop().time())

# =====================
# ADD SUB (ADMIN)
# =====================
async def add_sub(user_id: int, seconds: int):
    expire = int(asyncio.get_event_loop().time()) + seconds

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        INSERT INTO users (id, expire)
        VALUES (?, ?)
        ON CONFLICT(id) DO UPDATE SET expire=excluded.expire
        """, (user_id, expire))
        await db.commit()

# =====================
# START
# =====================
@dp.message(CommandStart())
async def start(msg: Message):
    await msg.answer(
        "👋 Привет!\n\n"
        "Этот бот выдаёт доступ после оплаты.\n"
        "Напиши /buy чтобы получить доступ."
    )

# =====================
# BUY (заглушка оплаты)
# =====================
@dp.message(Command("buy"))
async def buy(msg: Message):
    await msg.answer(
        "💳 Оплата:\n\n"
        "После оплаты админ выдаст доступ.\n"
        "Или напиши админу."
    )

# =====================
# CHECK ACCESS
# =====================
@dp.message(Command("check"))
async def check(msg: Message):
    active = await is_active(msg.from_user.id)

    if active:
        await msg.answer("✅ У тебя есть доступ")
    else:
        await msg.answer("❌ Доступ не активен")

# =====================
# ADMIN PANEL
# =====================
@dp.message(Command("admin"))
async def admin(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return

    await msg.answer(
        "🛠 АДМИН ПАНЕЛЬ\n\n"
        "/give ID DAYS - выдать доступ\n"
        "/users - список пользователей"
    )

# =====================
# GIVE SUB
# =====================
@dp.message(Command("give"))
async def give(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return

    try:
        _, user_id, days = msg.text.split()
        user_id = int(user_id)
        days = int(days)

        await add_sub(user_id, days * 86400)

        await msg.answer(f"✅ Доступ выдан пользователю {user_id} на {days} дней")

    except:
        await msg.answer("❌ Используй: /give ID DAYS")

# =====================
# USERS LIST
# =====================
@dp.message(Command("users"))
async def users(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, expire FROM users") as cur:
            rows = await cur.fetchall()

    text = "👥 USERS:\n\n"
    for r in rows:
        text += f"ID: {r[0]} | expire: {r[1]}\n"

    await msg.answer(text)

# =====================
# MAIN
# =====================
async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
