import asyncio
import os
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import aiosqlite
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ---------------- ENV ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler(timezone="Europe/Berlin")

# ---------------- DB ----------------
DB = "bot.db"

waiting_for_screen = set()

# ---------------- INIT DB ----------------
async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            expire_date TEXT,
            notified_3 INTEGER DEFAULT 0,
            notified_2 INTEGER DEFAULT 0,
            notified_1 INTEGER DEFAULT 0
        )
        """)
        await db.commit()

async def set_user(user_id, expire_date):
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        INSERT INTO users (user_id, expire_date)
        VALUES (?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET
            expire_date=excluded.expire_date,
            notified_3=0,
            notified_2=0,
            notified_1=0
        """, (user_id, expire_date))
        await db.commit()

async def get_user(user_id):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        return await cur.fetchone()

# ---------------- UI ----------------
def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Купить / Продлить", callback_data="buy")],
        [InlineKeyboardButton(text="📦 Подписка", callback_data="status")]
    ])

def buy_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 Отправить скрин", callback_data="send_screen")]
    ])

def renew_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Продлить", callback_data="buy")]
    ])

# ---------------- START ----------------
@dp.message(F.text == "/start")
async def start(msg: types.Message):
    user = await get_user(msg.from_user.id)

    if not user:
        await set_user(msg.from_user.id, None)

    await msg.answer(
        "✨ <b>Добро пожаловать!</b>\n"
        "💰 Подписка: 500₽ / 30 дней",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )

# ---------------- BUY ----------------
@dp.callback_query(F.data == "buy")
async def buy(call: types.CallbackQuery):
    await call.message.edit_text(
        "💳 <b>Оплата</b>\n\n"
        "Переведи 500₽ и отправь скрин 👇",
        reply_markup=buy_menu(),
        parse_mode="HTML"
    )

# ---------------- SCREEN ----------------
@dp.callback_query(F.data == "send_screen")
async def send_screen(call: types.CallbackQuery):
    waiting_for_screen.add(call.from_user.id)
    await call.message.answer("📸 Отправь скрин оплаты")

# ---------------- PHOTO ----------------
@dp.message(F.photo)
async def photo(msg: types.Message):
    if msg.from_user.id not in waiting_for_screen:
        return

    waiting_for_screen.remove(msg.from_user.id)

    photo = msg.photo[-1].file_id
    user_id = msg.from_user.id

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve_{user_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{user_id}")
        ]
    ])

    await bot.send_photo(
        ADMIN_ID,
        photo,
        caption=f"💰 Оплата\nID: {user_id}",
        reply_markup=kb
    )

    await msg.answer("⏳ Ожидай проверки")

# ---------------- APPROVE ----------------
@dp.callback_query(F.data.startswith("approve_"))
async def approve(call: types.CallbackQuery):
    user_id = int(call.data.split("_")[1])

    user = await get_user(user_id)
    now = datetime.now()

    if user and user[1]:
        try:
            old = datetime.fromisoformat(user[1])
            expire = old + timedelta(days=30) if old > now else now + timedelta(days=30)
        except:
            expire = now + timedelta(days=30)
    else:
        expire = now + timedelta(days=30)

    await set_user(user_id, expire.isoformat())

    invite = await bot.create_chat_invite_link(
        CHANNEL_ID,
        member_limit=1
    )

    await bot.send_message(
        user_id,
        f"🎉 Доступ открыт!\n📅 До: {expire.date()}\n\n🔗 {invite.invite_link}",
        reply_markup=renew_menu()
    )

    await call.message.edit_caption("✅ Подтверждено")

# ---------------- REJECT ----------------
@dp.callback_query(F.data.startswith("reject_"))
async def reject(call: types.CallbackQuery):
    user_id = int(call.data.split("_")[1])

    await bot.send_message(user_id, "❌ Платёж отклонён")
    await call.message.edit_caption("❌ Отклонено")

# ---------------- STATUS ----------------
@dp.callback_query(F.data == "status")
async def status(call: types.CallbackQuery):
    user = await get_user(call.from_user.id)

    if not user or not user[1]:
        await call.message.answer("❌ Нет подписки", reply_markup=renew_menu())
        return

    try:
        exp = datetime.fromisoformat(user[1])
    except:
        await call.message.answer("❌ Ошибка данных")
        return

    if datetime.now() > exp:
        await call.message.answer("⛔ Истекла", reply_markup=renew_menu())
    else:
        await call.message.answer(f"📦 До: {exp.date()}")

# ---------------- CHECK ----------------
async def check_users():
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("SELECT * FROM users")
        users = await cur.fetchall()

    now = datetime.now()

    for u in users:
        user_id, exp, n3, n2, n1 = u

        if not exp:
            continue

        try:
            exp = datetime.fromisoformat(exp)
        except:
            continue

        days = (exp - now).days

        if now > exp:
            try:
                await bot.ban_chat_member(CHANNEL_ID, user_id)
                await bot.unban_chat_member(CHANNEL_ID, user_id)
            except:
                pass

        elif days <= 3 and n3 == 0:
            await bot.send_message(user_id, "⚠️ 3 дня осталось")

        elif days <= 2 and n2 == 0:
            await bot.send_message(user_id, "⚠️ 2 дня осталось")

        elif days <= 1 and n1 == 0:
            await bot.send_message(user_id, "🚨 1 день остался")

# ---------------- ADMIN ----------------
def is_admin(uid):
    return uid == ADMIN_ID

@dp.message(F.text == "/admin")
async def admin(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return

    await msg.answer(
        "/users\n/adddays id days\n/ban id\n/unban id"
    )

@dp.message(F.text == "/users")
async def users(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return

    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("SELECT user_id, expire_date FROM users")
        data = await cur.fetchall()

    text = "👥 USERS:\n"
    for u in data[:30]:
        text += f"{u[0]} - {u[1]}\n"

    await msg.answer(text)

@dp.message(F.text.startswith("/adddays"))
async def adddays(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return

    _, uid, days = msg.text.split()
    uid, days = int(uid), int(days)

    user = await get_user(uid)
    now = datetime.now()

    if user and user[1]:
        try:
            exp = datetime.fromisoformat(user[1])
            exp = exp + timedelta(days=days)
        except:
            exp = now + timedelta(days=days)
    else:
        exp = now + timedelta(days=days)

    await set_user(uid, exp.isoformat())
    await msg.answer("✅ Added")

# ---------------- START ----------------
async def main():
    await init_db()
    scheduler.add_job(check_users, "interval", hours=6)
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())