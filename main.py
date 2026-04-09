import asyncio
import aiosqlite
from datetime import datetime, timedelta
import os

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties


# ================== CONFIG ==================
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()
DB = "bot.db"


# ================== DB ==================
async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            expire TEXT
        )
        """)
        await db.commit()


async def set_subscription(user_id: int, days: int = 30):
    expire = datetime.now() + timedelta(days=days)

    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        INSERT INTO users (user_id, expire)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET expire=excluded.expire
        """, (user_id, expire.isoformat()))
        await db.commit()


async def get_subscription(user_id: int):
    async with aiosqlite.connect(DB) as db:
        async with db.execute("SELECT expire FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            if not row:
                return None
            return datetime.fromisoformat(row[0])


async def is_active(user_id: int):
    exp = await get_subscription(user_id)
    return exp and exp > datetime.now()


# ================== UI (APP STYLE MENU) ==================
def app_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Подписка", callback_data="buy")],
        [InlineKeyboardButton(text="📊 Мой статус", callback_data="status")],
        [InlineKeyboardButton(text="⚙ Поддержка", callback_data="support")]
    ])


def buy_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Я оплатил", callback_data="paid")]
    ])


def admin_panel():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Пользователи", callback_data="admin_users")],
        [InlineKeyboardButton(text="💰 Активные подписки", callback_data="admin_active")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")]
    ])


def approve_btn(user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{user_id}")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{user_id}")]
    ])


# ================== START ==================
@dp.message(CommandStart())
async def start(message: Message):
    if not await is_active(message.from_user.id) and message.from_user.id != ADMIN_ID:
        await message.answer(
            "❌ <b>Доступ закрыт</b>\n\nОформи подписку ниже 👇",
            reply_markup=app_menu()
        )
        return

    await message.answer("🔥 <b>Добро пожаловать в систему</b>", reply_markup=app_menu())


# ================== BUY ==================
@dp.callback_query(F.data == "buy")
async def buy(call: CallbackQuery):
    await call.message.edit_text(
        "💎 <b>ПОДПИСКА PREMIUM</b>\n\n"
        "• 30 дней доступа\n"
        "• Полный контент\n"
        "• VIP доступ\n\n"
        "💰 Цена: 10€\n\n"
        "После оплаты нажми кнопку 👇",
        reply_markup=buy_menu()
    )


@dp.callback_query(F.data == "paid")
async def paid(call: CallbackQuery):
    await call.message.edit_text(
        "📤 Отправь сюда <b>скрин оплаты</b>"
    )


# ================== PAYMENT PROOF ==================
@dp.message(F.photo)
async def payment_photo(message: Message):
    if message.from_user.id == ADMIN_ID:
        return

    await bot.send_photo(
        ADMIN_ID,
        message.photo[-1].file_id,
        caption=f"💰 Заявка на доступ\nID: {message.from_user.id}",
        reply_markup=approve_btn(message.from_user.id)
    )

    await message.answer("⏳ Скрин отправлен на проверку")


# ================== ADMIN APPROVE ==================
@dp.callback_query(F.data.startswith("approve_"))
async def approve(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return

    user_id = int(call.data.split("_")[1])

    await set_subscription(user_id, 30)

    try:
        await bot.unban_chat_member(CHANNEL_ID, user_id)
    except:
        pass

    await bot.send_message(user_id, "✅ Доступ открыт на 30 дней 🔥")
    await call.message.edit_text("✅ Одобрено")


@dp.callback_query(F.data.startswith("reject_"))
async def reject(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return

    user_id = int(call.data.split("_")[1])
    await bot.send_message(user_id, "❌ Заявка отклонена")
    await call.message.edit_text("❌ Отклонено")


# ================== STATUS ==================
@dp.callback_query(F.data == "status")
async def status(call: CallbackQuery):
    exp = await get_subscription(call.from_user.id)

    if not exp:
        text = "❌ Подписки нет"
    else:
        text = f"📅 Активна до: <b>{exp.strftime('%Y-%m-%d %H:%M')}</b>"

    await call.message.edit_text(text, reply_markup=app_menu())


# ================== SUPPORT ==================
@dp.callback_query(F.data == "support")
async def support(call: CallbackQuery):
    await call.message.edit_text(
        "🛠 <b>Поддержка</b>\n\nНапиши админу: @admin",
        reply_markup=app_menu()
    )


# ================== ADMIN PANEL ==================
@dp.message(Command("admin"))
async def admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    await message.answer("⚙ <b>Админ панель</b>", reply_markup=admin_panel())


@dp.callback_query(F.data == "admin_users")
async def users(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    await call.message.edit_text("📊 Функция пользователей (можно расширить)", reply_markup=admin_panel())


# ================== ANTI-SLIP PROTECTION ==================
@dp.message(F.text)
async def protected_content(message: Message):
    if message.text.startswith("/"):
        return

    if not await is_active(message.from_user.id) and message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Нет доступа", reply_markup=app_menu())
        return

    await message.answer(
        "🔥 <b>Контент защищён</b>\n\n"
        "🚫 Пересылка запрещена",
        protect_content=True
    )


# ================== REMINDER ==================
async def reminder():
    while True:
        async with aiosqlite.connect(DB) as db:
            async with db.execute("SELECT user_id, expire FROM users") as cur:
                rows = await cur.fetchall()

                for user_id, exp in rows:
                    try:
                        exp = datetime.fromisoformat(exp)
                        days = (exp - datetime.now()).days

                        if days == 3:
                            await bot.send_message(user_id, "⚠️ Подписка истекает через 3 дня!")
                    except:
                        pass

        await asyncio.sleep(3600)


# ================== MAIN ==================
async def main():
    await init_db()
    asyncio.create_task(reminder())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
