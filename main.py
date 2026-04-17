import asyncio
import asyncpg
import os
import logging
import sys
from datetime import datetime

from aiohttp import web

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup,
    InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton,
    LabeledPrice, Update
)
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# ================= CONFIG =================
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "0").split(",")))
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
DATABASE_URL = os.getenv("DATABASE_URL")
CARD = os.getenv("CARD_NUMBER", "0000 0000 0000 0000")

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "secret")
BASE_URL = os.getenv("RENDER_EXTERNAL_URL")
WEBHOOK_URL = f"{BASE_URL}/webhook"

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# ================= TARIFS =================
PLANS = {
    "1m": {"days": 30, "price": 500, "stars": 250},
    "6m": {"days": 180, "price": 2750, "stars": 1300},
    "12m": {"days": 365, "price": 5500, "stars": 2600},
}

LOCK_DAYS = 27

# ================= STATES =================
class UserState(StatesGroup):
    wait_payment = State()
    support = State()

# ================= DB =================
async def init_db():
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            expire BIGINT DEFAULT 0,
            is_banned INT DEFAULT 0
        )
    """)
    await conn.close()

async def get_user(uid):
    conn = await asyncpg.connect(DATABASE_URL)
    row = await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", uid)
    await conn.close()
    return row

# ================= KEYBOARD =================
def kb(uid):
    k = [
        [KeyboardButton(text="💎 Купить"), KeyboardButton(text="📊 Статус")],
        [KeyboardButton(text="🆘 Поддержка")]
    ]
    if uid in ADMIN_IDS:
        k.append([KeyboardButton(text="⚙️ Админ")])
    return ReplyKeyboardMarkup(keyboard=k, resize_keyboard=True)

# ================= START =================
@dp.message(CommandStart())
async def start(message: Message):
    u = message.from_user

    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("""
        INSERT INTO users(user_id, username, first_name)
        VALUES($1,$2,$3)
        ON CONFLICT (user_id)
        DO UPDATE SET username=$2, first_name=$3
    """, u.id, u.username, u.first_name)
    await conn.close()

    await message.answer("🔥 VIP бот", reply_markup=kb(u.id))

# ================= STATUS =================
@dp.message(F.text == "📊 Статус")
async def status(message: Message):
    u = await get_user(message.from_user.id)
    exp = u["expire"] if u else 0

    now = int(datetime.now().timestamp())

    if exp > now:
        days = (exp - now)//86400
        await message.answer(f"🟢 Активна\nОсталось: {days} дн")
    else:
        await message.answer("🔴 Нет подписки")

# ================= BUY SYSTEM =================
@dp.message(F.text == "💎 Купить")
async def buy(message: Message, state: FSMContext):
    u = await get_user(message.from_user.id)
    exp = u["expire"] if u else 0

    now = int(datetime.now().timestamp())
    days_left = (exp - now)//86400 if exp > now else 0

    # ❌ ЛОК ПРОДЛЕНИЯ
    if days_left > 0:
        if days_left > 30:
            return await message.answer("❌ Долгосрочная подписка активна до окончания")
        if days_left >= LOCK_DAYS:
            return await message.answer("⏳ Продление пока недоступно")

    await state.set_state(UserState.wait_payment)

    await message.answer(
        "Выберите тариф:\n"
        "1m / 6m / 12m / ⭐",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="1 месяц")],
                [KeyboardButton(text="6 месяцев")],
                [KeyboardButton(text="12 месяцев")],
                [KeyboardButton(text="⭐ Stars")]
            ],
            resize_keyboard=True
        )
    )

# ================= PLAN SELECT =================
@dp.message(UserState.wait_payment, F.text.in_(["1 месяц","6 месяцев","12 месяцев"]))
async def select_plan(message: Message, state: FSMContext):

    mapping = {
        "1 месяц":"1m",
        "6 месяцев":"6m",
        "12 месяцев":"12m"
    }

    plan = mapping[message.text]
    await state.update_data(plan=plan)

    p = PLANS[plan]

    await message.answer(
        f"💳 {p['price']}₽\n"
        f"Карта: {CARD}\n\n"
        "Отправьте ФОТО чека"
    )

# ================= STARS =================
@dp.message(F.text == "⭐ Stars")
async def stars(message: Message):
    await message.answer(
        "Выберите Stars тариф:\n"
        "⭐ 1m / 6m / 12m"
    )

@dp.message(F.text.startswith("⭐"))
async def stars_invoice(message: Message):

    mapping = {
        "⭐ 1m":"1m",
        "⭐ 6m":"6m",
        "⭐ 12m":"12m"
    }

    if message.text not in mapping:
        return

    plan = mapping[message.text]
    p = PLANS[plan]

    prices = [LabeledPrice(label="VIP", amount=p["stars"]*100)]

    await bot.send_invoice(
        message.chat.id,
        title="VIP",
        description=f"{p['days']} дней",
        payload=plan,
        provider_token="",
        currency="XTR",
        prices=prices
    )

@dp.message(F.successful_payment)
async def success(message: Message):
    plan = message.successful_payment.invoice_payload
    p = PLANS.get(plan, PLANS["1m"])

    uid = message.from_user.id
    u = await get_user(uid)

    new_exp = max(u["expire"] if u else 0, int(datetime.now().timestamp())) + p["days"]*86400

    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("UPDATE users SET expire=$1 WHERE user_id=$2", new_exp, uid)
    await conn.close()

    link = await bot.create_chat_invite_link(CHANNEL_ID, member_limit=1)

    await message.answer(f"✅ Доступ:\n{link.invite_link}")

# ================= AUTO BAN SYSTEM =================
async def watcher():
    while True:
        conn = await asyncpg.connect(DATABASE_URL)
        now = int(datetime.now().timestamp())

        rows = await conn.fetch("SELECT * FROM users")

        for r in rows:
            uid = r["user_id"]
            exp = r["expire"]

            if exp <= now and exp > 0:
                try:
                    await bot.ban_chat_member(CHANNEL_ID, uid)
                    await bot.unban_chat_member(CHANNEL_ID, uid)
                    await bot.send_message(uid, "❌ подписка закончилась")
                except:
                    pass

                await conn.execute("UPDATE users SET expire=0 WHERE user_id=$1", uid)

        await conn.close()
        await asyncio.sleep(3600)

# ================= WEBHOOK =================
async def handle(request):
    data = await request.json()
    update = Update(**data)
    await dp.feed_update(bot, update)
    return web.Response()

async def on_start(app):
    await init_db()
    await bot.set_webhook(WEBHOOK_URL, secret_token=WEBHOOK_SECRET)
    asyncio.create_task(watcher())
    print("BOT STARTED")

async def on_stop(app):
    await bot.delete_webhook()

app = web.Application()
app.router.add_post("/webhook", handle)
app.on_startup.append(on_start)
app.on_shutdown.append(on_stop)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
