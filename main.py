import asyncio
import asyncpg
import os
import logging
import sys
from datetime import datetime

from aiohttp import web

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    Update, LabeledPrice
)
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart

# ================= CONFIG =================
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "0").split(",")))
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
DB = os.getenv("DATABASE_URL")

BASE_URL = os.getenv("RENDER_EXTERNAL_URL")
PORT = int(os.getenv("PORT", 10000))
WEBHOOK_PATH = "/webhook"

bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# ================= PLANS =================
PLANS = {
    "1m": {"days": 30, "rub": 500, "stars": 250},
    "6m": {"days": 180, "rub": 2450, "stars": 1300},
    "12m": {"days": 365, "rub": 5500, "stars": 2600},
}

# ================= DB =================
async def db():
    return await asyncpg.connect(DB)

# ================= INIT DB =================
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
        last_pay BIGINT DEFAULT 0,
        invite TEXT
    )
    """)
    await conn.close()

# ================= USER =================
async def get_user(uid):
    conn = await db()
    r = await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", uid)
    await conn.close()
    return r

# ================= KEYBOARD =================
def kb(uid):
    k = [
        [KeyboardButton(text="💎 Купить доступ")],
        [KeyboardButton(text="📊 Статус"), KeyboardButton(text="🆘 Поддержка")]
    ]
    if uid in ADMIN_IDS:
        k.append([KeyboardButton(text="⚙️ Админ")])
    return ReplyKeyboardMarkup(keyboard=k, resize_keyboard=True)

# ================= START =================
@dp.message(CommandStart())
async def start(m: Message):
    u = m.from_user

    conn = await db()
    await conn.execute("""
    INSERT INTO users VALUES($1,$2,$3,0,0,0,0,0,'')
    ON CONFLICT DO NOTHING
    """, u.id, u.username, u.first_name)
    await conn.close()

    await m.answer(f"🔥 <b>HARDHUB ACCESS</b>\n👤 {u.first_name}", reply_markup=kb(u.id))

# ================= STATUS =================
@dp.message(F.text == "📊 Статус")
async def status(m: Message):
    u = await get_user(m.from_user.id)
    now = int(datetime.now().timestamp())

    if u and u["expire"] > now:
        await m.answer(f"🟢 Активен\n⏳ {(u['expire']-now)//86400} дней")
    else:
        await m.answer("🔴 Нет доступа")

# ================= LOCK CHECK =================
def can_buy(u):
    now = int(datetime.now().timestamp())
    if not u:
        return True
    if u["expire"] > now:
        return False
    if now - (u["last_pay"] or 0) < 86400:
        return False
    return True

# ================= BUY =================
@dp.message(F.text == "💎 Купить доступ")
async def buy(m: Message):
    await m.answer("Выбери: 1m / 6m / 12m / ⭐")

# ================= RUB PAYMENT =================
@dp.message(F.text.in_(["1m","6m","12m"]))
async def pay_rub(m: Message):
    u = await get_user(m.from_user.id)
    plan = m.text

    if not can_buy(u):
        return await m.answer("⛔ Недоступно")

    p = PLANS[plan]

    await m.answer(
        f"💳 {p['rub']}₽\n"
        "Отправь ФОТО ЧЕКА"
    )

# ================= STARS =================
@dp.message(F.text == "⭐")
async def stars(m: Message):
    await m.answer("Напиши: ⭐ 1m / ⭐ 6m / ⭐ 12m")

@dp.message(F.text.startswith("⭐"))
async def stars_pay(m: Message):
    mp = {"⭐ 1m":"1m","⭐ 6m":"6m","⭐ 12m":"12m"}
    if m.text not in mp:
        return

    plan = mp[m.text]
    p = PLANS[plan]

    await bot.send_invoice(
        chat_id=m.chat.id,
        title="HARDHUB",
        description="VIP Access",
        payload=plan,
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice("VIP", p["stars"]*100)]
    )

# ================= PAYMENT CONFIRM =================
@dp.message(F.successful_payment)
async def paid(m: Message):
    plan = m.successful_payment.invoice_payload
    p = PLANS[plan]

    u = await get_user(m.from_user.id)
    now = int(datetime.now().timestamp())

    expire = max(u["expire"] if u else 0, now) + p["days"] * 86400

    conn = await db()
    await conn.execute("""
    UPDATE users SET expire=$1, last_pay=$2, stars_paid=stars_paid+$3
    WHERE user_id=$4
    """, expire, now, p["stars"], m.from_user.id)
    await conn.close()

    link = await bot.create_chat_invite_link(CHANNEL_ID, member_limit=1)

    await m.answer(f"🔓 Доступ:\n{link.invite_link}")

# ================= ADMIN =================
@dp.message(F.text == "⚙️ Админ")
async def admin(m: Message):
    if m.from_user.id not in ADMIN_IDS:
        return

    await m.answer("""
⚙️ ADMIN

/stats
/users
/ban id
/kick id
""")

# ================= STATS =================
@dp.message(F.text == "/stats")
async def stats(m: Message):
    if m.from_user.id not in ADMIN_IDS:
        return

    conn = await db()
    r = await conn.fetchrow("""
    SELECT SUM(rub_paid) rub, SUM(stars_paid) stars FROM users
    """)
    await conn.close()

    await m.answer(f"💰 {r['rub'] or 0} ₽\n⭐ {r['stars'] or 0}")

# ================= USERS =================
@dp.message(F.text == "/users")
async def users(m: Message):
    if m.from_user.id not in ADMIN_IDS:
        return

    conn = await db()
    rows = await conn.fetch("SELECT * FROM users")
    await conn.close()

    text = "👥 USERS\n\n"
    for r in rows:
        text += f"{r['user_id']} | {r['expire']}\n"

    await m.answer(text)

# ================= BAN =================
@dp.message(F.text.startswith("/ban"))
async def ban(m: Message):
    if m.from_user.id not in ADMIN_IDS:
        return

    uid = int(m.text.split()[1])

    conn = await db()
    await conn.execute("UPDATE users SET is_banned=1 WHERE user_id=$1", uid)
    await conn.close()

    await bot.ban_chat_member(CHANNEL_ID, uid)

# ================= AUTO KICK =================
async def watcher():
    while True:
        conn = await db()
        now = int(datetime.now().timestamp())

        users = await conn.fetch("SELECT * FROM users")

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
async def handler(request):
    data = await request.json()
    update = Update(**data)
    await dp.feed_update(bot, update)
    return web.Response()

async def on_start(app):
    await init_db()

    if not BASE_URL:
        raise Exception("No RENDER_EXTERNAL_URL")

    url = BASE_URL + WEBHOOK_PATH

    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(url)

    asyncio.create_task(watcher())

    print("HARDHUB LIVE:", url)

app = web.Application()
app.router.add_post(WEBHOOK_PATH, handler)
app.on_startup.append(on_start)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=PORT)
