import asyncio
import asyncpg
import os
import logging
from datetime import datetime

from aiohttp import web

from aiogram import Bot, Dispatcher, F
from aiogram.types import *
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart

# ================= SAFE CONFIG =================
def must(name):
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"ENV {name} NOT SET")
    return v

TOKEN = must("BOT_TOKEN")
DB = must("DATABASE_URL")
PUBLIC_URL = must("PUBLIC_URL")
CHANNEL_ID = int(must("CHANNEL_ID"))

ADMIN_IDS = set(map(int, os.getenv("ADMIN_IDS", "").split(",")))

PORT = int(os.getenv("PORT", 10000))

logging.basicConfig(level=logging.INFO)

bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

pool = None

# ================= PLANS =================
PLANS = {
    "1m": {"days": 30, "rub": 500, "stars": 0},
    "6m": {"days": 180, "rub": 2450, "stars": 1300},
    "12m": {"days": 365, "rub": 5500, "stars": 2600},
}

# ================= DB =================
async def init_db():
    global pool
    pool = await asyncpg.create_pool(DB, min_size=1, max_size=5)

    async with pool.acquire() as c:
        await c.execute("""
        CREATE TABLE IF NOT EXISTS users(
            user_id BIGINT PRIMARY KEY,
            expire BIGINT DEFAULT 0,
            last_pay BIGINT DEFAULT 0,
            banned INT DEFAULT 0
        )
        """)

        await c.execute("""
        CREATE TABLE IF NOT EXISTS payments(
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            plan TEXT,
            photo_id TEXT,
            status TEXT DEFAULT 'pending'
        )
        """)

# ================= USER =================
async def get_user(uid):
    async with pool.acquire() as c:
        return await c.fetchrow("SELECT * FROM users WHERE user_id=$1", uid)

# ================= KEYBOARD =================
def kb(uid):
    k = [
        [KeyboardButton(text="💎 Купить")],
        [KeyboardButton(text="📊 Статус")]
    ]
    if uid in ADMIN_IDS:
        k.append([KeyboardButton(text="⚙️ Админ")])
    return ReplyKeyboardMarkup(keyboard=k, resize_keyboard=True)

# ================= START =================
@dp.message(CommandStart())
async def start(m: Message):
    async with pool.acquire() as c:
        await c.execute("""
        INSERT INTO users(user_id)
        VALUES($1)
        ON CONFLICT DO NOTHING
        """, m.from_user.id)

    await m.answer("🔥 SaaS SYSTEM", reply_markup=kb(m.from_user.id))

# ================= STATUS =================
@dp.message(F.text == "📊 Статус")
async def status(m: Message):
    u = await get_user(m.from_user.id)
    now = int(datetime.now().timestamp())

    if u and u["expire"] > now:
        await m.answer("🟢 ACTIVE")
    else:
        await m.answer("🔴 NO ACCESS")

# ================= SHOP =================
@dp.message(F.text == "💎 Купить")
async def shop(m: Message):
    await m.answer(
        "💳 Выбери тариф:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="1 месяц - 500₽", callback_data="buy:1m")],
            [InlineKeyboardButton(text="6 месяцев - 2450₽", callback_data="buy:6m")],
            [InlineKeyboardButton(text="12 месяцев - 5500₽", callback_data="buy:12m")]
        ])
    )

# ================= BUY =================
@dp.callback_query(F.data.startswith("buy:"))
async def buy(c: CallbackQuery):
    plan = c.data.split(":")[1]

    await c.message.edit_text(
        "📸 Отправь фото оплаты (чек)"
    )

    dp.current_plan = plan

# ================= CHECK SUBMISSION =================
@dp.message(F.photo)
async def photo(m: Message):
    plan = getattr(dp, "current_plan", None)
    if not plan:
        return

    photo_id = m.photo[-1].file_id

    async with pool.acquire() as c:
        pid = await c.fetchval("""
        INSERT INTO payments(user_id, plan, photo_id)
        VALUES($1,$2,$3)
        RETURNING id
        """, m.from_user.id, plan, photo_id)

    for admin in ADMIN_IDS:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton("✅ APPROVE", callback_data=f"ok:{pid}"),
                InlineKeyboardButton("❌ REJECT", callback_data=f"no:{pid}")
            ]
        ])

        await bot.send_photo(admin, photo_id, caption=f"PAYMENT #{pid}", reply_markup=kb)

    await m.answer("⏳ Чек отправлен на проверку")

# ================= ADMIN APPROVE =================
async def activate(uid, plan):
    p = PLANS[plan]
    now = int(datetime.now().timestamp())

    async with pool.acquire() as c:
        u = await c.fetchrow("SELECT * FROM users WHERE user_id=$1", uid)

        exp = max(u["expire"] if u else 0, now) + p["days"] * 86400

        await c.execute("""
        UPDATE users SET expire=$1,last_pay=$2 WHERE user_id=$3
        """, exp, now, uid)

# ================= ADMIN HANDLERS =================
@dp.callback_query(F.data.startswith("ok:"))
async def ok(c: CallbackQuery):
    pid = int(c.data.split(":")[1])

    async with pool.acquire() as conn:
        p = await conn.fetchrow("SELECT * FROM payments WHERE id=$1", pid)
        await conn.execute("UPDATE payments SET status='approved' WHERE id=$1", pid)

    await activate(p["user_id"], p["plan"])
    await c.answer("APPROVED")

@dp.callback_query(F.data.startswith("no:"))
async def no(c: CallbackQuery):
    pid = int(c.data.split(":")[1])

    async with pool.acquire() as conn:
        await conn.execute("UPDATE payments SET status='rejected' WHERE id=$1", pid)

    await c.answer("REJECTED")

# ================= WEBHOOK =================
async def webhook(request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return web.Response(text="OK")

# ================= START =================
async def on_start(app):
    await init_db()

    url = f"{PUBLIC_URL}/webhook"

    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(url)

    asyncio.create_task(notifier())

    logging.info(f"WEBHOOK OK: {url}")

# ================= NOTIFIER =================
async def notifier():
    while True:
        now = int(datetime.now().timestamp())

        async with pool.acquire() as c:
            users = await c.fetch("SELECT user_id, expire FROM users")

        for u in users:
            left = (u["expire"] - now) // 86400

            if left in (3, 2, 1):
                try:
                    await bot.send_message(u["user_id"], f"⚠️ {left} days left")
                except:
                    pass

        await asyncio.sleep(3600)

# ================= APP =================
app = web.Application()
app.router.add_post("/webhook", webhook)
app.on_startup.append(on_start)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=PORT)
