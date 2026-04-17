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


# ================= CONFIG =================
TOKEN = os.getenv("BOT_TOKEN")
DB = os.getenv("DATABASE_URL")
PUBLIC_URL = os.getenv("PUBLIC_URL")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
PORT = int(os.getenv("PORT", 10000))

ADMIN_IDS = set(map(int, os.getenv("ADMIN_IDS", "").split(",")))

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


# ================= UI HELPERS (1000/10 STYLE) =================
def panel(title, text):
    return f"""
<b>╔══ {title} ══╗</b>

{text}

<b>╚══════════════╝</b>
"""

def status_ui(active, days=None):
    if active:
        return f"🟢 <b>ACTIVE</b>\n⏳ {days} days left"
    return "🔴 <b>NO ACCESS</b>"


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
            last_pay BIGINT DEFAULT 0
        )
        """)


async def get_user(uid):
    async with pool.acquire() as c:
        return await c.fetchrow("SELECT * FROM users WHERE user_id=$1", uid)


# ================= MAIN MENU UI =================
def main_menu(uid):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💎 Купить подписку")],
            [KeyboardButton(text="📊 Мой статус")],
            [KeyboardButton(text="🆘 Поддержка")]
        ],
        resize_keyboard=True
    )
    if uid in ADMIN_IDS:
        kb.keyboard.append([KeyboardButton(text="⚙️ Админ панель")])
    return kb


# ================= START =================
@dp.message(CommandStart())
async def start(m: Message):
    async with pool.acquire() as c:
        await c.execute("""
        INSERT INTO users(user_id, username, first_name)
        VALUES($1,$2,$3)
        ON CONFLICT DO NOTHING
        """, m.from_user.id, m.from_user.username, m.from_user.first_name)

    await m.answer(
        panel(
            "HARDHUB SaaS",
            "🔥 Добро пожаловать в закрытый сервис\n💳 Управление подпиской доступно ниже"
        ),
        reply_markup=main_menu(m.from_user.id)
    )


# ================= STATUS =================
@dp.message(F.text == "📊 Мой статус")
async def status(m: Message):
    u = await get_user(m.from_user.id)
    now = int(datetime.now().timestamp())

    if u and u["expire"] > now:
        days = (u["expire"] - now) // 86400
        await m.answer(panel("STATUS", status_ui(True, days)))
    else:
        await m.answer(panel("STATUS", status_ui(False)))


# ================= SHOP UI =================
@dp.message(F.text == "💎 Купить подписку")
async def shop(m: Message):
    await m.answer(
        panel(
            "TARIFFS",
            "💎 Выберите план подписки\n\n"
            "▪️ 1 месяц — 500₽\n"
            "▪️ 6 месяцев — 2450₽\n"
            "▪️ 12 месяцев — 5500₽"
        ),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔥 1 месяц", callback_data="buy:1m")],
            [InlineKeyboardButton(text="⚡ 6 месяцев", callback_data="buy:6m")],
            [InlineKeyboardButton(text="👑 12 месяцев", callback_data="buy:12m")]
        ])
    )


# ================= BUY UI =================
@dp.callback_query(F.data.startswith("buy:"))
async def buy(c: CallbackQuery):
    plan = c.data.split(":")[1]
    p = PLANS[plan]

    await c.message.edit_text(
        panel(
            "PAYMENT",
            f"💳 План: {plan}\n💰 Цена: {p['rub']}₽\n\n📸 Отправь чек (фото)"
        )
    )

    dp.current_plan = plan


# ================= PAYMENT CHECK =================
@dp.message(F.photo)
async def photo(m: Message):
    plan = getattr(dp, "current_plan", None)
    if not plan:
        return

    photo = m.photo[-1].file_id

    for admin in ADMIN_IDS:
        await bot.send_photo(
            admin,
            photo,
            caption=panel(
                "NEW PAYMENT",
                f"👤 User: {m.from_user.id}\n📦 Plan: {plan}"
            ),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton("✅ APPROVE", callback_data=f"ok:{m.from_user.id}:{plan}"),
                    InlineKeyboardButton("❌ REJECT", callback_data=f"no:{m.from_user.id}")
                ]
            ])
        )

    await m.answer("⏳ Чек отправлен на проверку")


# ================= APPROVE =================
@dp.callback_query(F.data.startswith("ok:"))
async def ok(c: CallbackQuery):
    _, uid, plan = c.data.split(":")
    uid = int(uid)

    p = PLANS[plan]
    now = int(datetime.now().timestamp())

    async with pool.acquire() as conn:
        u = await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", uid)
        exp = max(u["expire"] if u else 0, now) + p["days"] * 86400

        await conn.execute("""
        UPDATE users SET expire=$1, last_pay=$2 WHERE user_id=$3
        """, exp, now, uid)

    await bot.send_message(uid,
        panel(
            "ACCESS GRANTED",
            "✅ Подписка активирована\n🔥 Добро пожаловать"
        )
    )

    await c.answer("APPROVED")


# ================= ADMIN PANEL =================
@dp.message(F.text == "⚙️ Админ панель")
async def admin(m: Message):
    if m.from_user.id not in ADMIN_IDS:
        return

    await m.answer(
        panel(
            "ADMIN CRM",
            "📊 Управление системой\n👥 Пользователи\n💰 Платежи"
        ),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("📊 DASHBOARD", callback_data="dash")]
        ])
    )


# ================= DASH =================
@dp.callback_query(F.data == "dash")
async def dash(c: CallbackQuery):
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM users")
        active = await conn.fetchval("SELECT COUNT(*) FROM users WHERE expire > $1",
                                      int(datetime.now().timestamp()))

    await c.message.edit_text(
        panel(
            "DASHBOARD",
            f"👥 Users: {total}\n🟢 Active: {active}"
        )
    )


# ================= WEBHOOK =================
async def webhook(request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return web.Response(text="OK")


async def on_start(app):
    global pool
    await init_db()

    url = f"{PUBLIC_URL}/webhook"

    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(url)

    logging.info(f"WEBHOOK READY: {url}")


app = web.Application()
app.router.add_post("/webhook", webhook)
app.on_startup.append(on_start)


if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=PORT)
