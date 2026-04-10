import asyncio
import asyncpg
import os
import logging
import sys
from datetime import datetime

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

# ================= CONFIGURATION =================
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
DATABASE_URL = os.getenv("DATABASE_URL")
CARD = os.getenv("CARD_NUMBER", "0000 0000 0000 0000")
PRICE = int(os.getenv("PRICE", "500"))
DAYS = 30
LOCK_DAYS = 27 

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

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
    if uid == ADMIN_ID:
        buttons.append([KeyboardButton(text="⚙️ Админ-Центр")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, input_field_placeholder="Выберите пункт меню...")

# ================= USER FLOW =================

@dp.message(CommandStart())
@dp.message(StateFilter(None), lambda m: m.text not in ["💎 Оформить подписку", "📊 Мой статус", "🆘 Техподдержка", "⚙️ Админ-Центр"])
async def welcome_handler(message: Message, state: FSMContext):
    u = message.from_user
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("""
        INSERT INTO users (user_id, username, first_name) VALUES ($1, $2, $3) 
        ON CONFLICT (user_id) DO UPDATE SET username = $2, first_name = $3
    """, u.id, u.username, u.first_name)
    await conn.close()
    
    welcome_text = (
        f"<b>✨ Добро пожаловать в VIP Gallery, {u.first_name}!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Я — ваш автоматизированный помощник. Здесь вы можете получить доступ к закрытому контенту.\n\n"
        f"<b>Ваши преимущества:</b>\n"
        f"✅ Доступ в приватный канал на <b>{DAYS} дней</b>\n"
        f"✅ Моментальная выдача ссылки после подтверждения\n"
        f"✅ Прямая связь с администрацией\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Воспользуйтесь меню ниже для управления:</i>"
    )
    await message.answer(welcome_text, reply_markup=main_reply_kb(u.id))

@dp.message(F.text == "📊 Мой статус")
async def status_handler(message: Message, state: FSMContext):
    await state.clear()
    res = await get_user_data(message.from_user.id)
    exp = res['expire'] if res else 0
    if exp > datetime.now().timestamp():
        dt = datetime.fromtimestamp(exp).strftime('%d.%m.%Y в %H:%M')
        await message.answer(f"<b>🛡 Статус подписки:</b>\n━━━━━━━━━━━━━━━━━━━━\n● Доступ: 🟢 <code>Активен</code>\n● Истекает: <b>{dt}</b>")
    else:
        await message.answer("<b>🛡 Статус подписки:</b>\n━━━━━━━━━━━━━━━━━━━━\n● Доступ: 🔴 <code>Не активен</code>")

@dp.message(F.text == "💎 Оформить подписку")
async def buy_handler(message: Message, state: FSMContext):
    await state.clear()
    res = await get_user_data(message.from_user.id)
    exp = res['expire'] if res else 0
    if (exp - int(datetime.now().timestamp())) // 86400 >= LOCK_DAYS:
        return await message.answer("<b>⚠️ У вас еще активна подписка!</b>\nПродление станет доступно позже.")

    pay_text = (
        f"<b>💳 Оплата VIP-доступа на {DAYS} дней</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"● Стоимость: <b>{PRICE} ₽</b>\n"
        f"● Карта для перевода: <code>{CARD}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>📝 Что нужно сделать:</b>\n"
        f"1. Переведите сумму на указанную карту.\n"
        f"2. Пришлите <b>скриншот чека</b> сюда.\n\n"
        f"<i>Админ проверит платеж и бот выдаст вам ссылку.</i>"
    )
    await state.set_state(UserState.wait_screenshot)
    await message.answer(pay_text, reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="⬅️ Отмена")]], resize_keyboard=True))

@dp.message(F.text == "⬅️ Отмена", StateFilter(UserState.wait_screenshot))
async def cancel_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("<b>🏠 Главное меню</b>", reply_markup=main_reply_kb(message.from_user.id))

@dp.message(UserState.wait_screenshot, F.photo)
async def photo_handler(message: Message, state: FSMContext):
    await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, 
        caption=f"<b>💰 НОВЫЙ ЧЕК</b>\n👤 От: {message.from_user.mention_html()}\n🆔 ID: <code>{message.from_user.id}</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"ok:{message.from_user.id}"),
             InlineKeyboardButton(text="❌ Отказать", callback_data=f"no:{message.from_user.id}")]
        ]))
    await message.answer("<b>✅ Чек отправлен на проверку!</b>\nПожалуйста, ожидайте уведомления.")
    await state.clear()

# ================= SUPPORT =================

@dp.message(F.text == "🆘 Техподдержка")
async def support_init(message: Message, state: FSMContext):
    await state.set_state(UserState.in_support)
    await message.answer("<b>📟 Прямая связь с администратором.</b>\nНапишите ваш вопрос одним сообщением:")

@dp.message(UserState.in_support)
async def support_handler(message: Message):
    if message.text in ["💎 Оформить подписку", "📊 Мой статус", "🆘 Техподдержка", "⚙️ Админ-Центр"]: return
    await bot.send_message(ADMIN_ID, f"<b>📟 ВОПРОС ПОДДЕРЖКИ</b>\n🆔 ID: <code>{message.from_user.id}</code>\n👤 От: {message.from_user.mention_html()}\n\n💬: {message.text}")
    await message.answer("✅ <b>Ваше сообщение доставлено!</b> Ожидайте ответа.")

# ================= ADMIN ACTIONS =================

@dp.message(F.text == "⚙️ Админ-Центр")
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID: return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Список платников", callback_data="adm_list")],
        [InlineKeyboardButton(text="🔍 Поиск по ID", callback_data="adm_search")]
    ])
    await message.answer("<b>⚙️ Панель администратора</b>", reply_markup=kb)

@dp.callback_query(F.data == "adm_search")
async def admin_search(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminState.wait_id_search)
    await call.message.edit_text("🔎 Введите <b>ID</b> пользователя для управления:")

@dp.message(AdminState.wait_id_search)
async def admin_search_res(message: Message, state: FSMContext):
    if not message.text.isdigit(): return
    uid = int(message.text)
    res = await get_user_data(uid)
    if not res: return await message.answer("❌ Юзер не найден в базе.")
    is_active = res['expire'] > datetime.now().timestamp()
    st = "🚫 БАН" if res['is_banned'] else ("🟢 Активен" if is_active else "⚪️ Нет подписки")
    kb = [[InlineKeyboardButton(text="🔓 Разбанить" if res['is_banned'] else "🚫 ЗАБАНИТЬ", callback_data=f"ban:{uid}")]]
    if is_active: kb.append([InlineKeyboardButton(text="📉 Снять подписку (Kick)", callback_data=f"kick:{uid}")])
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="adm_back")])
    await message.answer(f"👤 <b>Карточка: {res['first_name']}</b>\n🆔 ID: <code>{uid}</code>\nСтатус: {st}", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await state.clear()

@dp.callback_query(F.data == "adm_back")
async def adm_back_btn(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="👥 Список", callback_data="adm_list")],[InlineKeyboardButton(text="🔍 Поиск", callback_data="adm_search")]])
    await call.message.edit_text("<b>⚙️ Панель администратора</b>", reply_markup=kb)

@dp.callback_query(F.data == "adm_list")
async def adm_list_show(call: CallbackQuery):
    conn = await asyncpg.connect(DATABASE_URL)
    rows = await conn.fetch("SELECT * FROM users WHERE expire > $1", int(datetime.now().timestamp()))
    await conn.close()
    res_text = "<b>👥 Действующие подписки:</b>\n\n" + "\n".join([f"• @{r['username']} (<code>{r['user_id']}</code>)" for r in rows]) if rows else "Список пуст."
    await call.message.edit_text(res_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="adm_back")]]))

@dp.callback_query(F.data.startswith("ok:"))
async def approve_pay(call: CallbackQuery):
    uid = int(call.data.split(":")[1])
    res = await get_user_data(uid)
    new_e = max(res['expire'] if res else 0, int(datetime.now().timestamp())) + (DAYS * 86400)
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("UPDATE users SET expire = $1 WHERE user_id = $2", new_e, uid)
    await conn.close()
    link = await bot.create_chat_invite_link(CHANNEL_ID, member_limit=1)
    await bot.send_message(uid, f"<b>✅ ВАША ОПЛАТА ПРИНЯТА!</b>\n━━━━━━━━━━━━━━━━━━━━\nСсылка для входа:\n{link.invite_link}\n\n⚠️ <i>Ссылка одноразовая!</i>")
    await call.message.edit_caption(caption=f"{call.message.caption}\n\n✅ <b>ОДОБРЕНО</b>")

@dp.callback_query(F.data.startswith("kick:"))
async def adm_kick_user(call: CallbackQuery):
    uid = int(call.data.split(":")[1])
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("UPDATE users SET expire = 0 WHERE user_id = $1", uid)
    await conn.close()
    try:
        await bot.ban_chat_member(CHANNEL_ID, uid)
        await bot.unban_chat_member(CHANNEL_ID, uid)
    except: pass
    await bot.send_message(uid, "⚠️ <b>Ваша подписка аннулирована!</b>")
    await call.answer("Юзер кикнут")
    await call.message.delete()

@dp.message(F.reply_to_message & (F.chat.id == ADMIN_ID))
async def admin_reply_handler(message: Message):
    try:
        target_text = message.reply_to_message.text or message.reply_to_message.caption
        tid = int(target_text.split("ID: ")[1].split("\n")[0])
        await bot.send_message(tid, f"<b>🔔 Ответ администратора:</b>\n\n{message.text}")
        await message.answer("✅ Доставлено.")
    except: await message.answer("❌ Ошибка ID.")

@dp.message.outer_middleware()
async def ban_middleware(handler, event, data):
    u = data.get("event_from_user")
    if u:
        r = await get_user_data(u.id)
        if r and r['is_banned']: return
    return await handler(event, data)

async def main():
    await init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
