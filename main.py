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
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart

# ================= CONFIG =================
TOKEN = os.getenv("BOT_TOKEN")
DB = os.getenv("DATABASE_URL")
PUBLIC_URL = os.getenv("PUBLIC_URL")
PORT = int(os.getenv("PORT", 10000))

ADMIN_IDS = set(map(int, os.getenv("ADMIN_IDS", "").split(",")))

logging.basicConfig(level=logging.INFO)

bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

pool: asyncpg.Pool | None = None


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

    async with pool.acquire() as conn:
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


async def get_user(uid: int):
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", uid)


# ================= KEYBOARD =================
def main_kb(uid):
    kb = [
        [KeyboardButton(text="💎 Купить")],
        [KeyboardButton(text="📊 Статус")]
    ]
    if uid in ADMIN_IDS:
        kb.append([KeyboardButton(text="⚙️ Админ")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


# ================= INVITE LOCK =================
async def create_invite(uid: int):
    link = await bot.create_chat_invite_link(
        chat_id=int(os.getenv("CHANNEL_ID")),
        member_limit=1,
        name=f"user_{uid}"
    )

    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET invite=$1 WHERE user_id=$2",
                           link.invite_link, uid)

    return link.invite_link


# ================= START =================
@dp.message(CommandStart())
async def start(m: Message):
    u = m.from_user

    async with pool.acquire() as conn:
        await conn.execute("""
        INSERT INTO users VALUES($1,$2,$3,0,0,0,0,0,NULL)
        ON CONFLICT DO NOTHING
        """, u.id, u.username, u.first_name)

    await m.answer("🔥 HARDHUB SYSTEM", reply_markup=main_kb(u.id))


# ================= STATUS =================
@dp.message(F.text == "📊 Статус")
async def status(m: Message):
    u = await get_user(m.from_user.id)
    now = int(datetime.now().timestamp())

    if u and u["expire"] > now:
        await m.answer(f"🟢 ACTIVE\n⏳ {(u['expire']-now)//86400} days left")
    else:
        await m.answer("🔴 NO ACCESS")


# ================= BUY =================
@dp.message(F.text == "💎 Купить")
async def buy(m: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1m - 500₽", callback_data="buy:1m")],
        [InlineKeyboardButton(text="6m - 2450₽ / 1300⭐", callback_data="buy:6m")],
        [InlineKeyboardButton(text="12m - 5500₽ / 2600⭐", callback_data="buy:12m")]
    ])

    await m.answer("💳 Choose plan", reply_markup=kb)


# ================= ANTI ABUSE =================
def can_buy(u):
    if not u:
        return True

    now = int(datetime.now().timestamp())

    if u["expire"] > now:
        return False

    if now - (u["last_pay"] or 0) < 86400 * 27:
        return False

    return True


# ================= BUY HANDLER =================
@dp.callback_query(F.data.startswith("buy:"))
async def buy_plan(c: CallbackQuery):
    plan = c.data.split(":")[1]
    p = PLANS[plan]

    u = await get_user(c.from_user.id)

    if not can_buy(u):
        return await c.answer("⛔ WAIT 27 DAYS AFTER EXPIRY", show_alert=True)

    await c.message.edit_text(
        f"💳 {p['rub']}₽ / ⭐ {p['stars']}\n\n📸 SEND PAYMENT PROOF"
    )


# ================= PAYMENT SUCCESS =================
async def payment_success(uid: int, plan: str, rub=0, stars=0):
    p = PLANS[plan]
    now = int(datetime.now().timestamp())

    async with pool.acquire() as conn:
        u = await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", uid)

        expire = max(u["expire"] if u else 0, now) + p["days"] * 86400

        await conn.execute("""
        UPDATE users
        SET expire=$1,
            last_pay=$2,
            rub_paid=rub_paid+$3,
            stars_paid=stars_paid+$4
        WHERE user_id=$5
        """, expire, now, rub, stars, uid)

    invite = await create_invite(uid)

    for admin in ADMIN_IDS:
        await bot.send_message(admin,
            f"💰 PAYMENT\nID:{uid}\nPLAN:{plan}\n₽:{rub} ⭐:{stars}"
        )

    await bot.send_message(uid,
        f"✅ ACCESS GRANTED\n🔗 {invite}\n⚠️ 1 user = 1 link"
    )


# ================= ADMIN =================
@dp.message(F.text == "⚙️ Админ")
async def admin(m: Message):
    if m.from_user.id not in ADMIN_IDS:
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 DASH", callback_data="adm:dash")],
        [InlineKeyboardButton(text="👥 USERS", callback_data="adm:users")]
    ])

    await m.answer("⚙️ ADMIN PANEL", reply_markup=kb)


# ================= DASH =================
@dp.callback_query(F.data == "adm:dash")
async def dash(c: CallbackQuery):
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM users")
        active = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE expire > $1",
            int(datetime.now().timestamp())
        )

    await c.message.edit_text(f"📊 DASHBOARD\n👥 {total}\n🟢 {active}")


# ================= USERS =================
@dp.callback_query(F.data == "adm:users")
async def users(c: CallbackQuery):
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id FROM users LIMIT 30")

    kb = []
    text = "👥 USERS\n\n"

    for r in rows:
        uid = r["user_id"]
        text += f"{uid}\n"
        kb.append([InlineKeyboardButton(text=str(uid), callback_data=f"user:{uid}")])

    await c.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))


# ================= USER CARD =================
@dp.callback_query(F.data.startswith("user:"))
async def user_card(c: CallbackQuery):
    uid = int(c.data.split(":")[1])
    u = await get_user(uid)

    if not u:
        return await c.answer("NOT FOUND")

    st = "🟢" if u["expire"] > int(datetime.now().timestamp()) else "🔴"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton("BAN", callback_data=f"ban:{uid}"),
            InlineKeyboardButton("UNBAN", callback_data=f"unban:{uid}")
        ],
        [
            InlineKeyboardButton("KICK", callback_data=f"kick:{uid}"),
            InlineKeyboardButton("RESET", callback_data=f"reset:{uid}")
        ]
    ])

    await c.message.edit_text(f"👤 USER {uid}\nSTATUS:{st}", reply_markup=kb)


# ================= EXPIRY NOTIFIER =================
async def notifier():
    while True:
        try:
            now = int(datetime.now().timestamp())

            async with pool.acquire() as conn:
                users = await conn.fetch("SELECT user_id, expire FROM users")

            for u in users:
                left = (u["expire"] - now) // 86400

                if left in (3, 2, 1):
                    try:
                        await bot.send_message(u["user_id"], f"⚠️ expires in {left} days")
                    except:
                        pass

        except Exception as e:
            logging.error(e)

        await asyncio.sleep(3600)


# ================= WEBHOOK =================
async def webhook(request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return web.Response(text="OK")


async def on_start(app):
    await init_db()

    if not PUBLIC_URL:
        raise RuntimeError("PUBLIC_URL NOT SET")

    url = f"{PUBLIC_URL}/webhook"

    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(url)

    asyncio.create_task(notifier())

    logging.info(f"WEBHOOK OK: {url}")


async def on_shutdown(app):
    await bot.session.close()
    if pool:
        await pool.close()


# ================= APP =================
app = web.Application()
app.router.add_post("/webhook", webhook)

app.on_startup.append(on_start)
app.on_cleanup.append(on_shutdown)


if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=PORT)
