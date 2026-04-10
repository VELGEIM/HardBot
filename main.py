import asyncio
import asyncpg
import os
import logging
import sys
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, 
    InlineKeyboardButton, ChatMemberUpdated, ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.filters import CommandStart, ChatMemberUpdatedFilter, IS_MEMBER
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# ================= CONFIG (ENVIRONMENT) =================
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
DATABASE_URL = os.getenv("DATABASE_URL")
CARD = os.getenv("CARD_NUMBER", "0000 0000 0000 0000")
PRICE = int(os.getenv("PRICE", "500"))
DAYS = 30
LOCK_DAYS = 27 

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

if not TOKEN or not DATABASE_URL:
    logger.critical("ОШИБКА: BOT_TOKEN или DATABASE_URL не найдены!")
    sys.exit(1)

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- States ---
class UserState(StatesGroup):
    wait_screenshot = State()
    in_support = State()

class AdminState(StatesGroup):
    wait_id_search = State()

# ================= DATABASE =================
async def init_db():
    try:
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
        logger.info("База данных PostgreSQL готова.")
    except Exception as e:
        logger.error(f"Ошибка БД: {e}")

async def get_user_data(uid):
    conn = await asyncpg.connect(DATABASE_URL)
    row = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", uid)
    await conn.close()
    return row

# ================= KEYBOARDS =================
def main_reply_kb(uid):
    buttons = [
        [KeyboardButton(text="💳 Купить/Продлить"), KeyboardButton(text="📊 Статус")],
        [KeyboardButton(text="🛠 Поддержка")]
    ]
    if uid == ADMIN_ID:
        buttons.append([KeyboardButton(text="👑 Админ Панель")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# ================= HANDLERS =================

@dp.message(CommandStart())
async def start_cmd(message: Message, state: FSMContext):
    await state.clear()
    u = message.from_user
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("""
        INSERT INTO users (user_id, username, first_name) VALUES ($1, $2, $3) 
        ON CONFLICT (user_id) DO UPDATE SET username = $2, first_name = $3
    """, u.id, u.username, u.first_name)
    await conn.close()
    await message.answer(
        f"👋 <b>Добро пожаловать, {u.first_name}!</b>\n\nИспользуйте меню внизу чата.", 
        reply_markup=main_reply_kb(u.id)
    )

@dp.message(F.text == "📊 Статус")
async def view_status(message: Message, state: FSMContext):
    await state.clear()
    res = await get_user_data(message.from_user.id)
    exp = res['expire'] if res else 0
    if exp > datetime.now().timestamp():
        dt = datetime.fromtimestamp(exp).strftime('%d.%m.%Y %H:%M')
        await message.answer(f"🟢 Подписка активна до:\n<b>{dt}</b>")
    else:
        await message.answer("🔴 У вас нет активной подписки.")

@dp.message(F.text == "💳 Купить/Продлить")
async def buy_start(message: Message, state: FSMContext):
    await state.clear()
    res = await get_user_data(message.from_user.id)
    exp = res['expire'] if res else 0
    days_left = (exp - int(datetime.now().timestamp())) // 86400
    
    if days_left >= LOCK_DAYS:
        return await message.answer(f"⚠️ Продление будет доступно позже (осталось {days_left} дн.)")
    
    await state.set_state(UserState.wait_screenshot)
    await message.answer(
        f"💳 <b>Оплата подписки (30 дней)</b>\n\n"
        f"Сумма: <b>{PRICE}₽</b>\n"
        f"Карта: <code>{CARD}</code>\n\n"
        f"<b>Пришлите скриншот чека одним сообщением:</b>"
    )

@dp.message(UserState.wait_screenshot, F.photo)
async def got_screenshot(message: Message, state: FSMContext):
    await bot.send_photo(
        ADMIN_ID, 
        message.photo[-1].file_id, 
        caption=f"💰 <b>НОВЫЙ ЧЕК</b>\nОт: {message.from_user.mention_html()}\nID: <code>{message.from_user.id}</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"ok:{message.from_user.id}"),
             InlineKeyboardButton(text="❌ Отказ", callback_data=f"no:{message.from_user.id}")]
        ])
    )
    await message.answer("⏳ Чек отправлен на проверку!")
    await state.clear()

@dp.message(F.text == "🛠 Поддержка")
async def support_init(message: Message, state: FSMContext):
    await state.set_state(UserState.in_support)
    await message.answer("📟 <b>Режим рации включен.</b>\nНапишите ваш вопрос админу. Для выхода нажмите любую кнопку меню.")

@dp.message(UserState.in_support)
async def support_chat(message: Message):
    if message.text in ["💳 Купить/Продлить", "📊 Статус", "👑 Админ Панель", "🛠 Поддержка"]:
        return
    await bot.send_message(
        ADMIN_ID, 
        f"📟 <b>СООБЩЕНИЕ ПОДДЕРЖКИ</b>\nID: <code>{message.from_user.id}</code>\nЮзер: {message.from_user.mention_html()}\n\n{message.text}"
    )
    await message.answer("✅ Отправлено. Ждите ответа.")

# ================= АДМИН-ЛОГИКА (ТУТ БЫЛА ОШИБКА) =================

@dp.callback_query(F.data.startswith("ok:"))
async def approve_pay(call: CallbackQuery):
    uid = int(call.data.split(":")[1])
    res = await get_user_data(uid)
    current_exp = res['expire'] if res else 0
    new_exp = max(current_exp, int(datetime.now().timestamp())) + (DAYS * 86400)
    
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("UPDATE users SET expire = $1 WHERE user_id = $2", new_exp, uid)
    await conn.close()
    
    link = await bot.create_chat_invite_link(CHANNEL_ID, member_limit=1)
    
    await bot.send_message(
        uid, 
        "✅ <b>Оплата подтверждена!</b>\n\n"
        f"Ваша ссылка для входа:\n{link.invite_link}\n\n"
        "⚠️ <b>Внимание:</b> Ссылка одноразовая!",
        protect_content=True
    )
    # Исправленное добавление текста к капче:
    new_caption = f"{call.message.caption}\n\n✅ ОДОБРЕНО"
    await call.message.edit_caption(caption=new_caption)

@dp.callback_query(F.data.startswith("no:"))
async def reject_pay(call: CallbackQuery):
    uid = int(call.data.split(":")[1])
    await bot.send_message(uid, "❌ Ваш чек не прошел проверку.")
    new_caption = f"{call.message.caption}\n\n❌ ОТКЛОНЕНО"
    await call.message.edit_caption(caption=new_caption)

@dp.message(F.reply_to_message & (F.chat.id == ADMIN_ID))
async def admin_reply(message: Message):
    try:
        target_id = int(message.reply_to_message.text.split("ID: ")[1].split("\n")[0])
        await bot.send_message(target_id, f"🔔 <b>Ответ поддержки:</b>\n\n{message.text}")
        user_state = dp.fsm.get_context(bot=bot, chat_id=target_id, user_id=target_id)
        await user_state.set_state(UserState.in_support)
        await message.answer("✅ Отправлено.")
    except:
        await message.answer("❌ Ошибка ID.")

@dp.message(F.text == "👑 Админ Панель")
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID: return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Список", callback_data="adm_list")]
    ])
    await message.answer("👑 Админка", reply_markup=kb)

@dp.callback_query(F.data == "adm_list")
async def adm_list(call: CallbackQuery):
    conn = await asyncpg.connect(DATABASE_URL)
    rows = await conn.fetch("SELECT * FROM users WHERE expire > $1", int(datetime.now().timestamp()))
    await conn.close()
    res = "👥 <b>Активные:</b>\n\n" + "\n".join([f"• @{r['username']} (<code>{r['user_id']}</code>)" for r in rows])
    await call.message.edit_text(res if rows else "Пусто.")

# ================= ЗАПУСК =================
async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
