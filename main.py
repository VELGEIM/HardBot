import asyncio
import aiosqlite
import os
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ChatJoinRequest
)
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup


# ================= CONFIG =================
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

CARD = "2200702134061840"
PRICE = 500
DAYS = 30

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
DB = "bot.db"


# ================= FSM =================
class PayState(StatesGroup):
    wait_screenshot = State()


# ================= DB =================
async def init_db():
    async with aiosqlite.connect(DB) as db:

        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
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


async def set_user(user_id: int, days: int = DAYS):
    expire = int((datetime.now() + timedelta(days=days)).timestamp())

    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT OR REPLACE INTO users VALUES (?, ?)",
            (user_id, expire)
        )
        await db.commit()


async def get_expire(user_id: int):
    async with aiosqlite.connect(DB) as db:
        async with db.execute(
            "SELECT expire FROM users WHERE user_id=?",
            (user_id,)
        ) as cur:
            row = await cur.fetchone()

    return row[0] if row else None


async def is_active(user_id: int):
    exp = await get_expire(user_id)
    if not exp:
        return False
    return exp > int(datetime.now().timestamp())


# ================= UI =================
def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Купить", callback_data="buy")],
        [InlineKeyboardButton(text="🔁 Продлить", callback_data="renew")],
        [InlineKeyboardButton(text="📊 Статус", callback_data="status")],
        [InlineKeyboardButton(text="🛠 Поддержка", callback_data="support")],
        [InlineKeyboardButton(text="👑 Админ", callback_data="admin")]
    ])


def admin_panel():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="users")],
        [InlineKeyboardButton(text="🔙 Выйти", callback_data="back")]
    ])


def pay_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 Я оплатил", callback_data="paid")]
    ])


def back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
    ])


def admin_kb(user_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"ok:{user_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"no:{user_id}")
        ]
    ])


# ================= START =================
@dp.message(CommandStart())
async def start(message: Message):
    active = await is_active(message.from_user.id)

    await message.answer(
        "🏠 <b>КАБИНЕТ</b>\n\n"
        f"Статус: {'🟢 Активна' if active else '🔴 Нет подписки'}\n\n"
        "Выбери действие 👇",
        reply_markup=main_menu()
    )


# ================= BUY =================
@dp.callback_query(F.data == "buy")
async def buy(call: CallbackQuery, state: FSMContext):
    await state.set_state(PayState.wait_screenshot)

    await call.message.edit_text(
        f"💳 <b>ОПЛАТА</b>\n\n"
        f"Цена: {PRICE}₽\n"
        f"Срок: {DAYS} дней\n\n"
        f"Карта: <code>{CARD}</code>",
        reply_markup=pay_kb()
    )


@dp.callback_query(F.data == "renew")
async def renew(call: CallbackQuery):
    await call.message.edit_text(
        f"🔁 <b>ПРОДЛЕНИЕ</b>\n\n"
        f"+{DAYS} дней = {PRICE}₽\n\n"
        f"Карта: <code>{CARD}</code>",
        reply_markup=pay_kb()
    )


@dp.callback_query(F.data == "paid")
async def paid(call: CallbackQuery):
    await call.message.answer("📸 Отправь скрин оплаты")


# ================= SCREENSHOT =================
@dp.message(PayState.wait_screenshot, F.photo)
async def screenshot(message: Message, state: FSMContext):
    photo = message.photo[-1].file_id

    await bot.send_photo(
        ADMIN_ID,
        photo,
        caption=f"💰 Оплата\nUser: {message.from_user.id}",
        reply_markup=admin_kb(message.from_user.id)
    )

    await message.answer("⏳ Ожидай проверки")
    await state.clear()


# ================= APPROVE =================
@dp.callback_query(F.data.startswith("ok:"))
async def approve(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return

    user_id = int(call.data.split(":")[1])

    await set_user(user_id, DAYS)

    try:
        await bot.approve_chat_join_request(CHANNEL_ID, user_id)
    except:
        pass

    await bot.send_message(user_id, "✅ Подписка активирована")
    await call.message.edit_text("OK")


# ================= STATUS =================
@dp.callback_query(F.data == "status")
async def status(call: CallbackQuery):
    exp = await get_expire(call.from_user.id)

    if not exp:
        await call.message.edit_text("❌ Нет подписки")
        return

    left = exp - int(datetime.now().timestamp())

    await call.message.edit_text(
        f"📊 <b>СТАТУС</b>\n\n"
        f"Осталось дней: {left // 86400}"
    )


# ================= ADMIN PANEL =================
@dp.callback_query(F.data == "admin")
async def admin(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Нет доступа", show_alert=True)

    await call.message.edit_text("👑 Админ-панель", reply_markup=admin_panel())


@dp.callback_query(F.data == "stats")
async def stats(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return

    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("SELECT COUNT(*) FROM users")
        users = (await cur.fetchone())[0]

    await call.message.answer(f"👥 Пользователей: {users}")


# ================= JOIN =================
@dp.chat_join_request()
async def join(req: ChatJoinRequest):
    if await is_active(req.from_user.id):
        await req.approve()
    else:
        await req.decline()


# ================= AUTO REMINDERS =================
async def reminders():
    while True:
        now = int(datetime.now().timestamp())

        async with aiosqlite.connect(DB) as db:
            async with db.execute("SELECT user_id, expire FROM users") as cur:
                users = await cur.fetchall()

            for user_id, exp in users:
                left_days = (exp - now) // 86400

                if left_days in [3, 2, 1]:

                    # проверка чтобы не спамить
                    check = await db.execute(
                        "SELECT 1 FROM reminders WHERE user_id=? AND stage=?",
                        (user_id, left_days)
                    )
                    exists = await check.fetchone()

                    if not exists:
                        try:
                            await bot.send_message(
                                user_id,
                                f"⚠️ ВНИМАНИЕ\n\n"
                                f"Твоя подписка закончится через <b>{left_days} дн.</b>"
                            )
                        except:
                            pass

                        await db.execute(
                            "INSERT INTO reminders VALUES (?, ?)",
                            (user_id, left_days)
                        )

            await db.commit()

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

                    await db.execute("DELETE FROM users WHERE user_id=?", (user_id,))

            await db.commit()

        await asyncio.sleep(3600)


# ================= MAIN =================
async def main():
    await init_db()
    asyncio.create_task(cleanup())
    asyncio.create_task(reminders())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
