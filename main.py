import asyncio
import asyncpg
import os
from aiohttp import web
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.types import *
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart

from ui import *
from crm import *
from security import *

TOKEN = os.getenv("BOT_TOKEN")
DB = os.getenv("DATABASE_URL")
PUBLIC_URL = os.getenv("PUBLIC_URL")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
ADMIN_IDS = set(map(int, os.getenv("ADMIN_IDS","").split(",")))

bot = Bot(TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

pool = None


# ================= DB =================
async def init_db():
    global pool
    pool = await asyncpg.create_pool(DB)

    async with pool.acquire() as c:
        await c.execute("""
        CREATE TABLE IF NOT EXISTS users(
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            expire BIGINT DEFAULT 0,
            is_banned INT DEFAULT 0,
            rub_paid BIGINT DEFAULT 0,
            last_pay BIGINT DEFAULT 0
        )
        """)


# ================= UI NAVIGATION SYSTEM =================
@dp.message(CommandStart())
async def start(m: Message):
    u = m.from_user

    async with pool.acquire() as c:
        await c.execute("""
        INSERT INTO users(user_id, username, first_name)
        VALUES($1,$2,$3)
        ON CONFLICT DO NOTHING
        """, u.id, u.username, u.first_name)

    user = await get_user(u.id)

    await m.answer(home(user), reply_markup=main_kb())


# ================= MENU =================
def main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("💎 STORE", callback_data="store")],
        [InlineKeyboardButton("📊 PROFILE", callback_data="profile")],
        [InlineKeyboardButton("📡 SUPPORT", callback_data="support")]
    ])


# ================= STORE =================
@dp.callback_query(F.data == "store")
async def store_h(c: CallbackQuery):
    await c.message.edit_text(store(), reply_markup=main_kb())


# ================= PROFILE (ANIMATED CRM CARD) =================
@dp.callback_query(F.data == "profile")
async def profile(c: CallbackQuery):
    u = await get_user(c.from_user.id)
    await c.message.edit_text(profile_card(u, True), reply_markup=main_kb())


# ================= SUPPORT RADIO =================
@dp.message()
async def support_router(m: Message):
    if m.from_user.id in ADMIN_IDS:
        return

    for a in ADMIN_IDS:
        await bot.send_message(a,
            f"📡 RADIO SUPPORT\nFROM: {m.from_user.id}\n\n{m.text}"
        )


# ================= ADMIN CRM =================
@dp.message(F.text == "/admin")
async def admin(m: Message):
    if m.from_user.id not in ADMIN_IDS:
        return

    async with pool.acquire() as c:
        total = await c.fetchval("SELECT COUNT(*) FROM users")
        active = await c.fetchval("SELECT COUNT(*) FROM users WHERE expire > $1",
                                   int(datetime.now().timestamp()))

    await m.answer(admin_dashboard(total, active, 0))


# ================= CALLBACK ENGINE =================
@dp.callback_query()
async def engine(c: CallbackQuery):
    if c.data.startswith("ban:"):
        uid = int(c.data.split(":")[1])
        await ban_user(uid)
        await c.answer("BANNED")

    if c.data.startswith("unban:"):
        uid = int(c.data.split(":")[1])
        await unban_user(uid)
        await c.answer("UNBANNED")


# ================= WEBHOOK =================
async def webhook(req):
    data = await req.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return web.Response(text="OK")


async def start_app(app):
    await init_db()
    await bot.set_webhook(f"{PUBLIC_URL}/webhook")


app = web.Application()
app.router.add_post("/webhook", webhook)
app.on_startup.append(start_app)

web.run_app(app, host="0.0.0.0", port=int(os.getenv("PORT",10000)))
