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


# ================= SAFE CONFIG =================
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))

CARD = "2200702134061840"
PRICE = 500
DAYS = 30

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

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
    return exp and exp > int(datetime.now().timestamp())


# ================= UI (CLEAN 100/10 DESIGN) =================
def is_admin(uid: int):
    return uid == ADMIN_ID


def home_kb(uid: int):
    kb = [
        [InlineKeyboardButton(text="💳 Купить подписку", callback_data="buy")],
        [InlineKeyboardButton(text="🔁 Продлить", callback_data="renew")],
        [InlineKeyboardButton(text="📊 Мой статус", callback_data="status")],
        [InlineKeyboardButton(text="🛠 Поддержка", callback_data="support")]
    ]

    if is_admin(uid):
        kb.append([InlineKeyboardButton(text="👑 Админ панель", callback_data="admin")])

    return InlineKeyboardMarkup(inline_keyboard=kb)


def back_home():
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
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton(text="⬅️ Выйти", callback_data="home")]
    ])


def admin_confirm_kb(user_id: int):
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
        "🏠 <b>ЛИЧНЫЙ КАБИНЕТ</b>\n\n"
        f"Статус: {'🟢 Активна' if active else '🔴 Нет подписки'}\n\n"
        "Выбери действие 👇",
        reply_markup=home_kb(message.from_user.id)
    )


# ================= NAVIGATION =================
@dp.callback_query(F.data == "home")
async def home(call: CallbackQuery):
    await call.message.edit_text(
        "🏠 <b>ГЛАВНОЕ МЕНЮ</b>\n\nВыберите действие 👇",
        reply_markup=home_kb(call.from_user.id)
    )


# ================= BUY =================
@dp.callback_query(F.data == "buy")
async def buy(call: CallbackQuery, state: FSMContext):
    await state.set_state(PayState.wait_screenshot)

    await call.message.edit_text(
        "💳 <b>ОПЛАТА ПОДПИСКИ</b>\n\n"
        f"Цена: <b>{PRICE}₽</b>\n"
        f"Срок: <b>{DAYS} дней</b>\n\n"
        f"Карта: <code>{CARD}</code>",
        reply_markup=pay_kb()
    )


@dp.callback_query(F.data == "renew")
async def renew(call: CallbackQuery):
    await call.message.edit_text(
        "🔁 <b>ПРОДЛЕНИЕ</b>\n\n"
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
        caption=f"💰 НОВАЯ ОПЛАТА\nUser: {message.from_user.id}",
        reply_markup=admin_confirm_kb(message.from_user.id)
    )

    await message.answer("⏳ Ожидай подтверждения")
    await state.clear()


# ================= APPROVE =================
@dp.callback_query(F.data.startswith("ok:"))
async def approve(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)

    user_id = int(call.data.split(":")[1])

    await set_user(user_id, DAYS)

    try:
        await bot.approve_chat_join_request(CHANNEL_ID, user_id)
    except:
        pass

    await bot.send_message(user_id, "✅ Подписка активирована")


# ================= STATUS =================
@dp.callback_query(F.data == "status")
async def status(call: CallbackQuery):
    exp = await get_expire(call.from_user.id)

    if not exp:
        await call.message.edit_text("❌ Подписка не найдена", reply_markup=back_home())
        return

    days_left = (exp - int(datetime.now().timestamp())) // 86400

    await call.message.edit_text(
        "📊 <b>СТАТУС</b>\n\n"
        f"Осталось: <b>{days_left} дней</b>",
        reply_markup=back_home()
    )


# ================= SUPPORT (FIXED REAL FSM) =================
@dp.callback_query(F.data == "support")
async def support(call: CallbackQuery, state: FSMContext):
    await state.set_state(SupportState.wait_text)

    await call.message.edit_text(
        "🛠 <b>ПОДДЕРЖКА</b>\n\nНапишите сообщение:",
        reply_markup=back_home()
    )


@dp.message(SupportState.wait_text)
async def support_msg(message: Message, state: FSMContext):
    await bot.send_message(
        ADMIN_ID,
        f"🛠 SUPPORT\nUser: {message.from_user.id}\n\n{message.text}"
    )

    await message.answer("✅ Отправлено", reply_markup=back_home())
    await state.clear()


# ================= ADMIN =================
@dp.callback_query(F.data == "admin")
async def admin(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("⛔ Нет доступа", show_alert=True)

    await call.message.edit_text("👑 АДМИН ПАНЕЛЬ", reply_markup=admin_panel())


@dp.callback_query(F.data == "stats")
async def stats(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return

    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("SELECT COUNT(*) FROM users")
        count = (await cur.fetchone())[0]

    await call.message.answer(f"👥 Пользователей: {count}")


# ================= JOIN CONTROL =================
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
                left = (exp - now) // 86400

                if left in [3, 2, 1]:
                    check = await db.execute(
                        "SELECT 1 FROM reminders WHERE user_id=? AND stage=?",
                        (user_id, left)
                    )

                    if not await check.fetchone():
                        try:
                            await bot.send_message(
                                user_id,
                                f"⚠️ Подписка закончится через <b>{left}</b> дней"
                            )
                        except:
                            pass

                        await db.execute(
                            "INSERT INTO reminders VALUES (?, ?)",
                            (user_id, left)
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
