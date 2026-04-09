import asyncio
import aiosqlite
import os
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ChatMemberUpdated
)
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup


# ================= CONFIG =================
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))

CARD = "2200702134061840"
PRICE = 500
DAYS = 30

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
DB = "bot.db"


# ================= STATES =================
class PayState(StatesGroup):
    wait_screenshot = State()

class SupportState(StatesGroup):
    wait_text = State()


# ================= DB =================
async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            expire INTEGER
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            user_id INTEGER,
            stage INTEGER,
            PRIMARY KEY(user_id, stage)
        )
        """)
        await db.commit()


async def save_user(user: Message):
    u = user.from_user
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        INSERT OR REPLACE INTO users (user_id, username, first_name, expire)
        VALUES (?, ?, ?, COALESCE((SELECT expire FROM users WHERE user_id=?), 0))
        """, (u.id, u.username, u.first_name, u.id))
        await db.commit()


async def set_user(user_id: int, days: int = DAYS):
    expire = int((datetime.now() + timedelta(days=days)).timestamp())
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        UPDATE users SET expire=? WHERE user_id=?
        """, (expire, user_id))
        await db.commit()


async def get_expire(user_id: int):
    async with aiosqlite.connect(DB) as db:
        async with db.execute("SELECT expire FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
    return row[0] if row else None


async def is_active(user_id: int):
    exp = await get_expire(user_id)
    return exp and exp > int(datetime.now().timestamp())


async def get_all_users():
    async with aiosqlite.connect(DB) as db:
        async with db.execute("SELECT * FROM users") as cur:
            return await cur.fetchall()


# ================= UNIQUE LINK =================
async def create_unique_link():
    link = await bot.create_chat_invite_link(
        chat_id=CHANNEL_ID,
        member_limit=1,
        expire_date=datetime.now() + timedelta(minutes=15)
    )
    return link.invite_link


# ================= UI =================
def is_admin(uid): return uid == ADMIN_ID


def home_kb(uid):
    kb = [
        [InlineKeyboardButton(text="💳 Купить", callback_data="buy")],
        [InlineKeyboardButton(text="🔁 Продлить", callback_data="renew")],
        [InlineKeyboardButton(text="📊 Статус", callback_data="status")],
        [InlineKeyboardButton(text="🛠 Поддержка", callback_data="support")]
    ]
    if is_admin(uid):
        kb.append([InlineKeyboardButton(text="👑 Админ", callback_data="admin")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="home")]
    ])


def pay_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 Я оплатил", callback_data="paid")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="home")]
    ])


def admin_panel():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Пользователи", callback_data="users")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="home")]
    ])


def confirm_kb(uid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅", callback_data=f"ok:{uid}"),
            InlineKeyboardButton(text="❌", callback_data=f"no:{uid}")
        ]
    ])


# ================= START =================
@dp.message(CommandStart())
async def start(message: Message):
    await save_user(message)

    active = await is_active(message.from_user.id)

    await message.answer(
        f"🏠 <b>Кабинет</b>\n\nСтатус: {'🟢 Активен' if active else '🔴 Нет'}",
        reply_markup=home_kb(message.from_user.id)
    )


# ================= BUY =================
@dp.callback_query(F.data == "buy")
async def buy(call: CallbackQuery, state: FSMContext):
    await state.set_state(PayState.wait_screenshot)

    await call.message.edit_text(
        f"💳 Оплата {PRICE}₽\n\nКарта:\n<code>{CARD}</code>",
        reply_markup=pay_kb()
    )


@dp.callback_query(F.data == "renew")
async def renew(call: CallbackQuery):
    await call.message.edit_text(
        f"🔁 Продление {PRICE}₽ / {DAYS} дней\n\n<code>{CARD}</code>",
        reply_markup=pay_kb()
    )


@dp.callback_query(F.data == "paid")
async def paid(call: CallbackQuery):
    await call.message.answer("📸 Пришли скрин")


# ================= SCREENSHOT =================
@dp.message(PayState.wait_screenshot, F.photo)
async def screenshot(message: Message, state: FSMContext):
    user = message.from_user

    await bot.send_photo(
        ADMIN_ID,
        message.photo[-1].file_id,
        caption=(
            f"💰 <b>ОПЛАТА</b>\n\n"
            f"ID: <code>{user.id}</code>\n"
            f"@{user.username}\n"
            f"{user.first_name}\n"
            f"<a href='tg://user?id={user.id}'>Открыть</a>"
        ),
        reply_markup=confirm_kb(user.id)
    )

    await message.answer("⏳ Жди подтверждения")
    await state.clear()


# ================= APPROVE =================
@dp.callback_query(F.data.startswith("ok:"))
async def approve(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return

    user_id = int(call.data.split(":")[1])

    await set_user(user_id)

    link = await create_unique_link()

    await bot.send_message(
        user_id,
        f"✅ Доступ выдан!\n\n🔗 {link}\n\n⏳ 15 минут / 1 вход"
    )


# ================= STATUS =================
@dp.callback_query(F.data == "status")
async def status(call: CallbackQuery):
    exp = await get_expire(call.from_user.id)

    if not exp:
        return await call.message.edit_text("❌ Нет подписки", reply_markup=back_kb())

    days = (exp - int(datetime.now().timestamp())) // 86400

    await call.message.edit_text(
        f"📊 Осталось: {days} дней",
        reply_markup=back_kb()
    )


# ================= SUPPORT =================
@dp.callback_query(F.data == "support")
async def support(call: CallbackQuery, state: FSMContext):
    await state.set_state(SupportState.wait_text)
    await call.message.edit_text("🛠 Напиши сообщение", reply_markup=back_kb())


@dp.message(SupportState.wait_text)
async def support_msg(message: Message, state: FSMContext):
    await bot.send_message(
        ADMIN_ID,
        f"🛠 SUPPORT\n{message.from_user.id}\n{message.text}"
    )
    await message.answer("✅ Отправлено")
    await state.clear()


# ================= ADMIN =================
@dp.callback_query(F.data == "admin")
async def admin(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    await call.message.edit_text("👑 Админ", reply_markup=admin_panel())


@dp.callback_query(F.data == "users")
async def users(call: CallbackQuery):
    rows = await get_all_users()

    text = "👤 Пользователи\n\n"

    for u in rows:
        text += f"{u[2]} (@{u[1]})\n"

    await call.message.answer(text)


@dp.callback_query(F.data == "stats")
async def stats(call: CallbackQuery):
    rows = await get_all_users()
    await call.message.answer(f"👥 Всего: {len(rows)}")


# ================= REMINDERS =================
async def reminders():
    while True:
        now = int(datetime.now().timestamp())

        async with aiosqlite.connect(DB) as db:
            async with db.execute("SELECT user_id, expire FROM users") as cur:
                users = await cur.fetchall()

            for user_id, exp in users:
                left = (exp - now) // 86400

                if left in [3, 2, 1]:
                    try:
                        await bot.send_message(
                            user_id,
                            f"⚠️ Осталось {left} дней"
                        )
                    except:
                        pass

        await asyncio.sleep(3600)


# ================= CLEANUP =================
async def cleanup():
    while True:
        now = int(datetime.now().timestamp())

        async with aiosqlite.connect(DB) as db:
            async with db.execute("SELECT user_id, expire FROM users") as cur:
                rows = await cur.fetchall()

            for user_id, exp in rows:
                if exp < now:
                    try:
                        await bot.ban_chat_member(CHANNEL_ID, user_id)
                        await bot.unban_chat_member(CHANNEL_ID, user_id)
                    except:
                        pass

        await asyncio.sleep(3600)


# ================= MAIN =================
async def main():
    await init_db()
    asyncio.create_task(reminders())
    asyncio.create_task(cleanup())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
