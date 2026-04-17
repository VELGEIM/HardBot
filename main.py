import asyncio
import asyncpg
import os
import logging
from datetime import datetime

from aiohttp import web

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    Update
)
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart


# ================= CONFIG =================
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = set(map(int, os.getenv("ADMIN_IDS", "").split(",")))
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
DB = os.getenv("DATABASE_URL")
BASE_URL = os.getenv("RENDER_EXTERNAL_URL")
PORT = int(os.getenv("PORT", 10000))

bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)

# ================= PLANS =================
PLANS = {
    "1m": {"days": 30, "rub": 500, "stars": 250},
    "6m": {"days": 180, "rub": 2450, "stars": 1300},
    "12m": {"days": 365, "rub": 5500, "stars": 2600},
}

# ================= DB =================
async def db():
    return await asyncpg.connect(DB)

async def init_db():
    conn = await db()
    await conn.execute("""
    CREATE TABLE IF NOT EXISTS users(
        user_id BIGINT PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        expire BIGINT DEFAULT 0,
        is_banned INT DEFAULT 0,
        rub_paid BIGINT DEFAULT 0,
        stars_paid BIGINT DEFAULT 0,
        last_pay BIGINT DEFAULT 0
    )
    """)
    await conn.close()

async def get_user(uid):
    conn = await db()
    u = await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", uid)
    await conn.close()
    return u


# ================= KEYBOARD =================
def user_kb(uid):
    kb = [
        [KeyboardButton(text="💎 Купить")],
        [KeyboardButton(text="📊 Статус"), KeyboardButton(text="🆘 Поддержка")]
    ]

    if uid in ADMIN_IDS:
        kb.append([KeyboardButton(text="⚙️ Админ")])

    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


# ================= START =================
@dp.message(CommandStart())
async def start(m: Message):
    u = m.from_user

    conn = await db()
    await conn.execute("""
    INSERT INTO users VALUES($1,$2,$3,0,0,0,0,0)
    ON CONFLICT DO NOTHING
    """, u.id, u.username, u.first_name)
    await conn.close()

    await m.answer("🔥 <b>HARDHUB</b>", reply_markup=user_kb(u.id))


# ================= STATUS =================
@dp.message(F.text == "📊 Статус")
async def status(m: Message):
    u = await get_user(m.from_user.id)
    now = int(datetime.now().timestamp())

    if u and u["expire"] > now:
        await m.answer(f"🟢 Активен\n⏳ {((u['expire']-now)//86400)} дней")
    else:
        await m.answer("🔴 Нет доступа")


# ================= BUY =================
@dp.message(F.text == "💎 Купить")
async def buy(m: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 мес - 500₽", callback_data="buy:1m")],
        [InlineKeyboardButton(text="6 мес - 2450₽ / 1300⭐", callback_data="buy:6m")],
        [InlineKeyboardButton(text="12 мес - 5500₽ / 2600⭐", callback_data="buy:12m")]
    ])

    await m.answer("💳 Выбери тариф:", reply_markup=kb)


# ================= CHECK BUY =================
def can_buy(u):
    now = int(datetime.now().timestamp())
    if not u:
        return True
    if u["expire"] > now:
        return False
    if now - (u["last_pay"] or 0) < 86400:
        return False
    return True


# ================= PAYMENT MENU =================
@dp.callback_query(F.data.startswith("buy:"))
async def buy_plan(c: CallbackQuery):
    plan = c.data.split(":")[1]
    p = PLANS[plan]

    u = await get_user(c.from_user.id)
    if not can_buy(u):
        return await c.answer("⛔ Уже активна подписка", show_alert=True)

    await c.message.edit_text(
        f"💳 <b>Оплата</b>\n\n"
        f"Цена: {p['rub']}₽\n"
        f"ИЛИ ⭐ {p['stars'] if 'stars' in p else '-'}\n\n"
        "📸 ОТПРАВЬ ТОЛЬКО ФОТО ЧЕКА (НЕ PDF, НЕ ФАЙЛ)"
    )


# ================= ADMIN PANEL =================
@dp.message(F.text == "⚙️ Админ")
async def admin(m: Message):
    if m.from_user.id not in ADMIN_IDS:
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Дашборд", callback_data="adm:dash")],
        [InlineKeyboardButton(text="👥 Юзеры", callback_data="adm:users")],
        [InlineKeyboardButton(text="💰 Доход", callback_data="adm:money")]
    ])

    await m.answer("⚙️ ADMIN PANEL", reply_markup=kb)


# ================= DASH =================
@dp.callback_query(F.data == "adm:dash")
async def dash(c: CallbackQuery):
    conn = await db()

    users = await conn.fetchval("SELECT COUNT(*) FROM users")
    active = await conn.fetchval("SELECT COUNT(*) FROM users WHERE expire > $1", int(datetime.now().timestamp()))

    await conn.close()

    await c.message.edit_text(
        f"📊 DASHBOARD\n\n👥 {users}\n🟢 {active}"
    )


# ================= USERS =================
@dp.callback_query(F.data == "adm:users")
async def users(c: CallbackQuery):
    conn = await db()
    rows = await conn.fetch("SELECT user_id, expire FROM users LIMIT 20")
    await conn.close()

    text = "👥 USERS\n\n"
    for r in rows:
        text += f"{r['user_id']} | {r['expire']}\n"

    await c.message.edit_text(text)


# ================= MONEY =================
@dp.callback_query(F.data == "adm:money")
async def money(c: CallbackQuery):
    conn = await db()

    r = await conn.fetchrow("""
    SELECT SUM(rub_paid) rub, SUM(stars_paid) stars FROM users
    """)

    await conn.close()

    await c.message.edit_text(
        f"💰 ДОХОД\n\n₽ {r['rub'] or 0}\n⭐ {r['stars'] or 0}"
    )


# ================= AUTO KICK =================
async def watcher():
    while True:
        conn = await db()
        now = int(datetime.now().timestamp())

        users = await conn.fetch("SELECT user_id, expire FROM users")

        for u in users:
            if u["expire"] and u["expire"] <= now:
                try:
                    await bot.ban_chat_member(CHANNEL_ID, u["user_id"])
                    await bot.unban_chat_member(CHANNEL_ID, u["user_id"])
                except:
                    pass

                await conn.execute("UPDATE users SET expire=0 WHERE user_id=$1", u["user_id"])

        await conn.close()
        await asyncio.sleep(3600)


# ================= WEBHOOK =================
async def webhook(request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return web.Response()


async def on_start(app):
    await init_db()

    if not BASE_URL:
        raise Exception("NO RENDER URL")

    url = BASE_URL + "/webhook"

    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(url)

    asyncio.create_task(watcher())


app = web.Application()
app.router.add_post("/webhook", webhook)
app.on_startup.append(on_start)


if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=PORT)
