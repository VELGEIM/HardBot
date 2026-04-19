import asyncio
import asyncpg
import os
import sys
import socket

LOCK_FILE = "/tmp/bot.lock"

if os.path.exists(LOCK_FILE):
    print("Bot already running")
    sys.exit()

with open(LOCK_FILE, "w") as f:
    f.write(str(os.getpid()))

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup,
    InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.filters import CommandStart, StateFilter
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
PRICE = int(os.getenv("PRICE", "500"))
DAYS = 30
LOCK_DAYS = 27

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ================= STATES =================
class UserState(StatesGroup):
    wait_screenshot = State()
    in_support = State()


class AdminState(StatesGroup):
    wait_id_search = State()


# ================= DATABASE =================
async def init_db():
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            expire BIGINT DEFAULT 0,
            is_banned INTEGER DEFAULT 0
        )
    """)
    await conn.close()


async def get_user_data(uid):
    conn = await asyncpg.connect(DATABASE_URL)
    row = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", uid)
    await conn.close()
    return row


# ================= KEYBOARDS =================
def main_reply_kb(uid):
    buttons = [
        [KeyboardButton(text="💎 Оформить подписку"), KeyboardButton(text="📊 Мой статус")],
        [KeyboardButton(text="🆘 Техподдержка")]
    ]
    if is_admin(uid):
        buttons.append([KeyboardButton(text="⚙️ Админ-Центр")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


# ================= USER =================
@dp.message(CommandStart())
@dp.message(StateFilter(None))
async def welcome_handler(message: Message, state: FSMContext):
    u = message.from_user

    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("""
        INSERT INTO users (user_id, username, first_name)
        VALUES ($1, $2, $3)
        ON CONFLICT (user_id)
        DO UPDATE SET username = $2, first_name = $3
    """, u.id, u.username, u.first_name)
    await conn.close()

    text = (
        f"<b>✨ Добро пожаловать, {u.first_name}!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔐 VIP доступ к закрытому контенту\n\n"
        f"✔️ Доступ на {DAYS} дней\n"
        f"✔️ Моментальная выдача\n"
        f"✔️ Поддержка 24/7\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )

    await message.answer(text, reply_markup=main_reply_kb(u.id))


@dp.message(F.text == "📊 Мой статус")
async def status_handler(message: Message, state: FSMContext):
    await state.clear()
    res = await get_user_data(message.from_user.id)
    exp = res['expire'] if res else 0

    if exp > datetime.now().timestamp():
        dt = datetime.fromtimestamp(exp).strftime('%d.%m.%Y %H:%M')
        await message.answer(f"🟢 Активна до: {dt}")
    else:
        await message.answer("🔴 Подписка не активна")


@dp.message(F.text == "💎 Оформить подписку")
async def buy_handler(message: Message, state: FSMContext):
    await state.clear()

    pay_text = (
        f"<b>💳 ОПЛАТА VIP</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 {PRICE} ₽ | 📅 {DAYS} дней\n"
        f"💳 <code>{CARD}</code>\n\n"
        f"<b>❗ ВАЖНО</b>\n"
        f"Принимаются ТОЛЬКО ФОТО\n"
        f"❌ НЕ PDF\n"
        f"❌ НЕ файл\n\n"
        f"<i>Иначе чек не пройдет!</i>"
    )

    await state.set_state(UserState.wait_screenshot)
    await message.answer(pay_text,
                         reply_markup=ReplyKeyboardMarkup(
                             keyboard=[[KeyboardButton(text="⬅️ Отмена")]],
                             resize_keyboard=True))


@dp.message(F.text == "⬅️ Отмена")
async def cancel_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🏠 Главное меню", reply_markup=main_reply_kb(message.from_user.id))


# ================= PHOTO =================
@dp.message(UserState.wait_screenshot, F.photo)
async def photo_handler(message: Message, state: FSMContext):
    for admin in ADMIN_IDS:
        await bot.send_photo(
            admin,
            message.photo[-1].file_id,
            caption=f"💰 Чек от {message.from_user.id}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅", callback_data=f"ok:{message.from_user.id}"),
                    InlineKeyboardButton(text="❌", callback_data=f"no:{message.from_user.id}")
                ]
            ])
        )

    await message.answer("✅ Отправлено на проверку")
    await state.clear()


@dp.message(UserState.wait_screenshot)
async def wrong_handler(message: Message):
    await message.answer("❌ Только ФОТО!")


# ================= SUPPORT =================
@dp.message(F.text == "🆘 Техподдержка")
async def support_init(message: Message, state: FSMContext):
    await state.set_state(UserState.in_support)
    await message.answer("Напишите проблему\n⬅️ Отмена для выхода")


@dp.message(UserState.in_support)
async def support_handler(message: Message):
    for admin in ADMIN_IDS:
        await bot.send_message(admin, f"SUPPORT {message.from_user.id}: {message.text}")
    await message.answer("✅ Отправлено")


# ================= ADMIN =================
@dp.message(F.text == "⚙️ Админ-Центр")
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Список", callback_data="list")],
        [InlineKeyboardButton(text="Поиск", callback_data="search")]
    ])
    await message.answer("Админ панель", reply_markup=kb)


@dp.callback_query(F.data.startswith("ok:"))
async def approve(call: CallbackQuery):
    uid = int(call.data.split(":")[1])

    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("UPDATE users SET expire=$1 WHERE user_id=$2",
                       int(datetime.now().timestamp()) + DAYS * 86400, uid)
    await conn.close()

    link = await bot.create_chat_invite_link(CHANNEL_ID, member_limit=1)

    await bot.send_message(uid, f"✅ Доступ:\n{link.invite_link}")
    await call.message.edit_caption("✅ ОДОБРЕНО")


# ================= MAIN =================
async def main():
    await init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

os.remove("/tmp/bot.lock")
if __name__ == "__main__":
    asyncio.run(main())
