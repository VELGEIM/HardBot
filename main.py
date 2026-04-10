import asyncio
import asyncpg
import os
import logging
import sys
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, 
    InlineKeyboardButton, ChatMemberUpdated
)
from aiogram.filters import CommandStart, ChatMemberUpdatedFilter, IS_MEMBER
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# ================= CONFIG (RENDER ENV) =================
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
DATABASE_URL = os.getenv("DATABASE_URL")

CARD = os.getenv("CARD_NUMBER", "0000 0000 0000 0000")
PRICE = int(os.getenv("PRICE", "500"))
DAYS = 30
LOCK_DAYS = 27 

# Настройка логов для Render
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

if not TOKEN or not DATABASE_URL:
    logger.critical("CRITICAL ERROR: BOT_TOKEN or DATABASE_URL is missing!")
    sys.exit(1)

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- States ---
class PayState(StatesGroup): wait_screenshot = State()
class SupportState(StatesGroup): wait_text = State()
class AdminState(StatesGroup): wait_id_search = State()

# --- Database Logic (PostgreSQL) ---
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
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Database init error: {e}")

async def get_user_data(uid):
    conn = await asyncpg.connect(DATABASE_URL)
    row = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", uid)
    await conn.close()
    return row

# --- Keyboards ---
def home_kb(uid):
    kb = [
        [InlineKeyboardButton(text=f"💳 Купить/Продлить ({DAYS} дн.)", callback_data="buy")],
        [InlineKeyboardButton(text="📊 Статус подписки", callback_data="status")],
        [InlineKeyboardButton(text="🛠 Поддержка", callback_data="support")]
    ]
    if uid == ADMIN_ID:
        kb.append([InlineKeyboardButton(text="👑 Админ Панель", callback_data="admin_main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

# --- Handlers ---

# 1. Логгер входа в канал
@dp.chat_member(ChatMemberUpdatedFilter(member_status_changed=IS_MEMBER))
async def on_user_join(event: ChatMemberUpdated):
    u = event.from_user
    logger.info(f"User {u.id} joined the channel.")
    if ADMIN_ID:
        await bot.send_message(
            ADMIN_ID, 
            f"📥 <b>ВХОД В КАНАЛ</b>\nЮзер: {u.full_name}\nЛогин: @{u.username or 'нет'}\nID: <code>{u.id}</code>"
        )

# 2. Старт / Главное меню
@dp.message(CommandStart())
@dp.callback_query(F.data == "home")
async def start(event: Message | CallbackQuery, state: FSMContext):
    await state.clear()
    u = event.from_user
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("""
        INSERT INTO users (user_id, username, first_name) 
        VALUES ($1, $2, $3) 
        ON CONFLICT (user_id) DO UPDATE SET username = $2, first_name = $3
    """, u.id, u.username, u.first_name)
    await conn.close()
    
    txt = "🏠 <b>Главное меню</b>\n\nИспользуйте кнопки ниже для управления подпиской."
    if isinstance(event, Message):
        await event.answer(txt, reply_markup=home_kb(u.id))
    else:
        await event.message.edit_text(txt, reply_markup=home_kb(u.id))

# 3. Логика покупки
@dp.callback_query(F.data == "buy")
async def buy_process(call: CallbackQuery, state: FSMContext):
    res = await get_user_data(call.from_user.id)
    exp = res['expire'] if res else 0
    days_left = (exp - int(datetime.now().timestamp())) // 86400
    
    if days_left >= LOCK_DAYS:
        return await call.answer(f"⚠️ У вас еще {days_left} дн. подписки. Продление будет доступно позже.", show_alert=True)
    
    await state.set_state(PayState.wait_screenshot)
    await call.message.edit_text(
        f"💳 <b>Оплата доступа</b>\n\n"
        f"Цена: <b>{PRICE}₽</b>\n"
        f"Срок: <b>{DAYS} дней</b>\n\n"
        f"Карта для перевода:\n<code>{CARD}</code>\n\n"
        f"<b>Пришлите скриншот чека одним сообщением:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Отмена", callback_data="home")]])
    )

@dp.message(PayState.wait_screenshot, F.photo)
async def handle_screenshot(message: Message, state: FSMContext):
    u = message.from_user
    await bot.send_photo(
        ADMIN_ID, 
        message.photo[-1].file_id, 
        caption=f"💰 <b>НОВЫЙ ЧЕК</b>\nОт: {u.full_name}\nЛогин: @{u.username or 'нет'}\nID: <code>{u.id}</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"ok:{u.id}"),
             InlineKeyboardButton(text="❌ Отказ", callback_data=f"no:{u.id}")],
            [InlineKeyboardButton(text="🚫 ЗАБАНИТЬ", callback_data=f"ban:{u.id}")]
        ])
    )
    await message.answer("⏳ Чек отправлен на проверку. Вам придет уведомление.")
    await state.clear()

# 4. Админские действия (Одобрение/Отказ/Бан)
@dp.callback_query(F.data.startswith("ok:"))
async def approve_pay(call: CallbackQuery):
    uid = int(call.data.split(":")[1])
    res = await get_user_data(uid)
    new_exp = max(res['expire'] if res else 0, int(datetime.now().timestamp())) + (DAYS * 86400)
    
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("UPDATE users SET expire = $1 WHERE user_id = $2", new_exp, uid)
    await conn.close()
    
    link = await bot.create_chat_invite_link(CHANNEL_ID, member_limit=1)
    await bot.send_message(uid, f"✅ Оплата принята!\n\nВаша ссылка на канал:\n{link.invite_link}", protect_content=True)
    await call.message.edit_caption(caption=call.message.caption + "\n\n✅ ОДОБРЕНО")

@dp.callback_query(F.data.startswith("no:"))
async def reject_pay(call: CallbackQuery):
    uid = int(call.data.split(":")[1])
    await bot.send_message(uid, "❌ Ваша оплата не подтверждена. Проверьте данные или напишите в поддержку.")
    await call.message.edit_caption(caption=call.message.caption + "\n\n❌ ОТКЛОНЕНО")

@dp.callback_query(F.data.startswith("ban:"))
async def ban_user(call: CallbackQuery):
    uid = int(call.data.split(":")[1])
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("UPDATE users SET is_banned = 1 WHERE user_id = $1", uid)
    await conn.close()
    try:
        await bot.ban_chat_member(CHANNEL_ID, uid)
    except: pass
    await call.message.delete()
    await call.answer("Пользователь забанен и удален", show_alert=True)

# 5. Поддержка (Реплеи)
@dp.callback_query(F.data == "support")
async def support_init(call: CallbackQuery, state: FSMContext):
    await state.set_state(SupportState.wait_text)
    await call.message.edit_text("💬 Напишите ваш вопрос админу:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="home")]]))

@dp.message(SupportState.wait_text)
async def support_process(message: Message, state: FSMContext):
    await bot.send_message(ADMIN_ID, f"❓ <b>ВОПРОС</b>\nID: <code>{message.from_user.id}</code>\n\n{message.text}\n\n<i>(Ответьте реплеем)</i>")
    await message.answer("🚀 Отправлено!")
    await state.clear()

@dp.message(F.reply_to_message & (F.chat.id == ADMIN_ID))
async def admin_reply(message: Message):
    try:
        tid = int(message.reply_to_message.text.split("ID: ")[1].split("\n")[0])
        await bot.send_message(tid, f"🔔 <b>Ответ поддержки:</b>\n\n{message.text}")
        await message.answer("✅ Отправлено.")
    except: await message.answer("❌ Ошибка: ID не найден.")

# 6. Статус
@dp.callback_query(F.data == "status")
async def view_status(call: CallbackQuery):
    res = await get_user_data(call.from_user.id)
    exp = res['expire'] if res else 0
    if exp > datetime.now().timestamp():
        t = f"🟢 Активна до: {datetime.fromtimestamp(exp).strftime('%d.%m.%Y %H:%M')}"
    else: t = "🔴 Нет активной подписки."
    await call.message.edit_text(t, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="home")]]))

# 7. Админка
@dp.callback_query(F.data == "admin_main")
async def admin_panel(call: CallbackQuery):
    kb = [
        [InlineKeyboardButton(text="👥 Все платники", callback_data="adm_list")],
        [InlineKeyboardButton(text="🔍 Найти по ID", callback_data="adm_search")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="home")]
    ]
    await call.message.edit_text("👑 <b>Панель управления</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "adm_list")
async def admin_list(call: CallbackQuery):
    conn = await asyncpg.connect(DATABASE_URL)
    rows = await conn.fetch("SELECT * FROM users WHERE expire > $1", int(datetime.now().timestamp()))
    await conn.close()
    txt = "👥 <b>Список активных:</b>\n\n"
    for r in rows:
        txt += f"• @{r['username'] or 'no_user'} (ID: <code>{r['user_id']}</code>)\n"
    await call.message.edit_text(txt if rows else "Платников пока нет.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_main")]]))

@dp.callback_query(F.data == "adm_search")
async def search_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminState.wait_id_search)
    await call.message.edit_text("Введите ID пользователя:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Отмена", callback_data="admin_main")]]))

@dp.message(AdminState.wait_id_search)
async def search_result(message: Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("Только цифры.")
    res = await get_user_data(int(message.text))
    if not res: return await message.answer("Не найден в базе.")
    
    st = "🚫 БАН" if res['is_banned'] else ("🟢 Ок" if res['expire'] > datetime.now().timestamp() else "⚪️ Нет")
    await message.answer(
        f"👤 {res['first_name']} (@{res['username']})\nID: <code>{res['user_id']}</code>\nСтатус: {st}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚫 БАН", callback_data=f"ban:{res['user_id']}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_main")]
        ])
    )
    await state.clear()

# --- Middleware (Анти-бан) ---
@dp.message.outer_middleware()
async def ban_check(handler, event, data):
    u = data.get("event_from_user")
    if u:
        res = await get_user_data(u.id)
        if res and res['is_banned']: return
    return await handler(event, data)

# ================= RUN =================
async def main():
    await init_db()
    logger.info("Starting bot polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
