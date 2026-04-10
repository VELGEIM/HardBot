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

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- States ---
class UserState(StatesGroup):
    wait_screenshot = State()
    in_support = State()

class AdminState(StatesGroup):
    wait_id_search = State()

# ================= DATABASE (POSTGRESQL) =================
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
        [KeyboardButton(text="💳 Купить/Продлить"), KeyboardButton(text="📊 Статус")],
        [KeyboardButton(text="🛠 Поддержка")]
    ]
    if uid == ADMIN_ID:
        buttons.append([KeyboardButton(text="👑 Админ Панель")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def admin_inline_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Список платников", callback_data="adm_list")],
        [InlineKeyboardButton(text="🔍 Управление по ID", callback_data="adm_search")]
    ])

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
    await message.answer(f"👋 Привет, {u.first_name}!", reply_markup=main_reply_kb(u.id))

@dp.message(F.text == "📊 Статус")
async def view_status(message: Message, state: FSMContext):
    await state.clear()
    res = await get_user_data(message.from_user.id)
    exp = res['expire'] if res else 0
    if exp > datetime.now().timestamp():
        dt = datetime.fromtimestamp(exp).strftime('%d.%m.%Y %H:%M')
        await message.answer(f"🟢 Подписка активна до: <b>{dt}</b>")
    else:
        await message.answer("🔴 У вас нет активной подписки.")

@dp.message(F.text == "💳 Купить/Продлить")
async def buy_start(message: Message, state: FSMContext):
    await state.clear()
    res = await get_user_data(message.from_user.id)
    exp = res['expire'] if res else 0
    if (exp - int(datetime.now().timestamp())) // 86400 >= LOCK_DAYS:
        return await message.answer("⚠️ Продление доступно позже.")
    
    await state.set_state(UserState.wait_screenshot)
    await message.answer(f"💳 <b>Оплата {PRICE}₽</b>\nКарта: <code>{CARD}</code>\nПришлите скриншот чека:")

@dp.message(UserState.wait_screenshot, F.photo)
async def got_screenshot(message: Message, state: FSMContext):
    await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, 
        caption=f"💰 <b>ЧЕК</b>\nОт: {message.from_user.mention_html()}\nID: <code>{message.from_user.id}</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Ок", callback_data=f"ok:{message.from_user.id}"),
             InlineKeyboardButton(text="❌ Отказ", callback_data=f"no:{message.from_user.id}")]
        ]))
    await message.answer("⏳ Чек отправлен!")
    await state.clear()

@dp.message(F.text == "🛠 Поддержка")
async def support_init(message: Message, state: FSMContext):
    await state.set_state(UserState.in_support)
    await message.answer("📟 <b>Рация включена.</b> Опишите проблему:")

@dp.message(UserState.in_support)
async def support_chat(message: Message):
    if message.text in ["💳 Купить/Продлить", "📊 Статус", "👑 Админ Панель", "🛠 Поддержка"]: return
    await bot.send_message(ADMIN_ID, f"📟 <b>ПОДДЕРЖКА</b>\nID: <code>{message.from_user.id}</code>\n\n{message.text}")
    await message.answer("✅ Отправлено админу.")

# ================= SUPER ADMIN PANEL =================

@dp.message(F.text == "👑 Админ Панель")
async def admin_main(message: Message):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("👑 <b>Управление ботом</b>", reply_markup=admin_inline_kb())

@dp.callback_query(F.data == "adm_search")
async def adm_search_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminState.wait_id_search)
    await call.message.edit_text("🔎 Введите Telegram ID пользователя для управления:")

@dp.message(AdminState.wait_id_search)
async def adm_search_res(message: Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("Введите ID цифрами.")
    uid = int(message.text)
    res = await get_user_data(uid)
    if not res: return await message.answer("Юзер не найден в базе.")
    
    is_active = res['expire'] > datetime.now().timestamp()
    status = "🚫 ЗАБАНЕН" if res['is_banned'] else ("🟢 Активен" if is_active else "⚪️ Нет подписки")
    
    kb = []
    # Кнопка бана/разбана
    kb.append([InlineKeyboardButton(text="🔓 Разбанить" if res['is_banned'] else "🚫 Забанить и удалить", 
                                  callback_data=f"adm_ban:{uid}")])
    # Кнопка снятия подписки (если она есть)
    if is_active and not res['is_banned']:
        kb.append([InlineKeyboardButton(text="📉 Снять подписку (Аннулировать)", callback_data=f"adm_kick:{uid}")])
    
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="adm_back")])
    
    await message.answer(
        f"👤 {res['first_name']} (@{res['username']})\nID: <code>{uid}</code>\nСтатус: {status}", 
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )
    await state.clear()

@dp.callback_query(F.data.startswith("adm_ban:"))
async def adm_ban_toggle(call: CallbackQuery):
    uid = int(call.data.split(":")[1])
    res = await get_user_data(uid)
    new_state = 0 if res['is_banned'] else 1
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("UPDATE users SET is_banned = $1 WHERE user_id = $2", new_state, uid)
    await conn.close()
    
    if new_state == 1: # Бан
        try: await bot.ban_chat_member(CHANNEL_ID, uid)
        except: pass
        await call.answer("Пользователь забанен", show_alert=True)
    else: # Разбан
        try: await bot.unban_chat_member(CHANNEL_ID, uid, only_if_banned=True)
        except: pass
        await call.answer("Пользователь разбанен", show_alert=True)
    await call.message.delete()

@dp.callback_query(F.data.startswith("adm_kick:"))
async def adm_kick_user(call: CallbackQuery):
    uid = int(call.data.split(":")[1])
    # Обнуляем подписку в базе
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("UPDATE users SET expire = 0 WHERE user_id = $1", uid)
    await conn.close()
    # Удаляем из канала (бан и сразу разбан, чтобы мог зайти снова если купит)
    try:
        await bot.ban_chat_member(CHANNEL_ID, uid)
        await bot.unban_chat_member(CHANNEL_ID, uid)
    except: pass
    
    await bot.send_message(uid, "⚠️ Ваша подписка была аннулирована администратором за нарушение правил.")
    await call.answer("Подписка снята, юзер удален", show_alert=True)
    await call.message.delete()

# --- Остальная логика (админские действия) ---
@dp.callback_query(F.data == "adm_list")
async def adm_list(call: CallbackQuery):
    conn = await asyncpg.connect(DATABASE_URL)
    rows = await conn.fetch("SELECT * FROM users WHERE expire > $1", int(datetime.now().timestamp()))
    await conn.close()
    res = "👥 <b>Активные:</b>\n\n" + "\n".join([f"• @{r['username']} (<code>{r['user_id']}</code>)" for r in rows])
    await call.message.edit_text(res if rows else "Пусто.", reply_markup=admin_inline_kb())

@dp.callback_query(F.data == "adm_back")
async def adm_back_btn(call: CallbackQuery):
    await call.message.edit_text("👑 <b>Управление ботом</b>", reply_markup=admin_inline_kb())

@dp.callback_query(F.data.startswith("ok:"))
async def approve(call: CallbackQuery):
    uid = int(call.data.split(":")[1])
    res = await get_user_data(uid)
    new_exp = max(res['expire'] if res else 0, int(datetime.now().timestamp())) + (DAYS * 86400)
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("UPDATE users SET expire = $1 WHERE user_id = $2", new_exp, uid)
    await conn.close()
    link = await bot.create_chat_invite_link(CHANNEL_ID, member_limit=1)
    await bot.send_message(uid, f"✅ Одобрено! Ссылка:\n{link.invite_link}")
    await call.message.edit_caption(caption=f"{call.message.caption}\n\n✅ ОДОБРЕНО")

@dp.callback_query(F.data.startswith("no:"))
async def reject(call: CallbackQuery):
    uid = int(call.data.split(":")[1])
    await bot.send_message(uid, "❌ Оплата отклонена.")
    await call.message.edit_caption(caption=f"{call.message.caption}\n\n❌ ОТКЛОНЕНО")

@dp.message(F.reply_to_message & (F.chat.id == ADMIN_ID))
async def admin_reply(message: Message):
    try:
        target_id = int(message.reply_to_message.text.split("ID: ")[1].split("\n")[0])
        await bot.send_message(target_id, f"🔔 <b>Ответ админа:</b>\n\n{message.text}")
        state = dp.fsm.get_context(bot=bot, chat_id=target_id, user_id=target_id)
        await state.set_state(UserState.in_support)
        await message.answer("✅ Отправлено.")
    except: await message.answer("Ошибка ID.")

@dp.message.outer_middleware()
async def check_ban(handler, event, data):
    u = data.get("event_from_user")
    if u:
        res = await get_user_data(u.id)
        if res and res['is_banned']: return
    return await handler(event, data)

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
