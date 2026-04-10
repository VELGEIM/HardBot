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
from aiogram.filters import CommandStart
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
@dp.message(lambda m: m.text not in ["💎 Оформить подписку", "📊 Мой статус", "🆘 Техподдержка", "⚙️ Админ-Центр"], state=None)
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
        f"Я — ваш автоматизированный помощник. С моей помощью вы можете получить доступ к закрытому контенту.\n\n"
        f"<b>Что вы получаете:</b>\n"
        f"✅ Доступ в приватный канал на <b>{DAYS} дней</b>\n"
        f"✅ Регулярные обновления контента\n"
        f"✅ Прямая связь с поддержкой 24/7\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Воспользуйтесь меню ниже, чтобы начать:</i>"
    )
    await message.answer(welcome_text, reply_markup=main_reply_kb(u.id))

@dp.message(F.text == "📊 Мой статус")
async def status_handler(message: Message, state: FSMContext):
    await state.clear()
    res = await get_user_data(message.from_user.id)
    exp = res['expire'] if res else 0
    
    if exp > datetime.now().timestamp():
        dt = datetime.fromtimestamp(exp).strftime('%d.%m.%Y в %H:%M')
        await message.answer(
            f"<b>🛡 Информация о доступе:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"● Статус: 🟢 <code>Активен</code>\n"
            f"● Истекает: <b>{dt}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"✨ Приятного времяпровождения в канале!"
        )
    else:
        await message.answer(
            f"<b>🛡 Информация о доступе:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"● Статус: 🔴 <code>Не активен</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Для получения доступа нажмите кнопку <b>«💎 Оформить подписку»</b>"
        )

@dp.message(F.text == "💎 Оформить подписку")
async def buy_handler(message: Message, state: FSMContext):
    await state.clear()
    res = await get_user_data(message.from_user.id)
    exp = res['expire'] if res else 0
    days_left = (exp - int(datetime.now().timestamp())) // 86400
    
    if days_left >= LOCK_DAYS:
        return await message.answer(f"<b>⚠️ У вас еще активна подписка!</b>\nПродление будет доступно, когда останется менее 3-х дней.")

    pay_text = (
        f"<b>💳 Оформление VIP-доступа</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"● Срок действия: <b>{DAYS} дней</b>\n"
        f"● Стоимость: <b>{PRICE} ₽</b>\n\n"
        f"<b>Реквизиты для оплаты (Карта):</b>\n"
        f"<code>{CARD}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>📝 Инструкция:</b>\n"
        f"1. Переведите сумму на карту выше.\n"
        f"2. Сделайте скриншот чека.\n"
        f"3. <b>Пришлите скриншот сюда</b> в ответ на это сообщение.\n\n"
        f"<i>После проверки вы получите одноразовую ссылку на вход.</i>"
    )
    await state.set_state(UserState.wait_screenshot)
    await message.answer(pay_text, reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="⬅️ Отмена")]], resize_keyboard=True))

@dp.message(F.text == "⬅️ Отмена", state=UserState.wait_screenshot)
async def cancel_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("<b>🏠 Возврат в главное меню...</b>", reply_markup=main_reply_kb(message.from_user.id))

@dp.message(UserState.wait_screenshot, F.photo)
async def photo_handler(message: Message, state: FSMContext):
    await bot.send_photo(
        ADMIN_ID, 
        message.photo[-1].file_id, 
        caption=(
            f"<b>💰 НОВЫЙ ЧЕК НА ПРОВЕРКУ</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Отправитель: {message.from_user.mention_html()}\n"
            f"🆔 ID: <code>{message.from_user.id}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        ),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"ok:{message.from_user.id}"),
             InlineKeyboardButton(text="❌ Отклонить", callback_data=f"no:{message.from_user.id}")]
        ])
    )
    await message.answer("<b>✅ Чек успешно отправлен!</b>\nАдминистратор проверит его в ближайшее время. Пожалуйста, ожидайте уведомления.", reply_markup=main_reply_kb(message.from_user.id))
    await state.clear()

# ================= SUPPORT (RADIO MODE) =================

@dp.message(F.text == "🆘 Техподдержка")
async def support_init(message: Message, state: FSMContext):
    await state.set_state(UserState.in_support)
    await message.answer(
        "<b>📟 Режим прямой связи с админом</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        "Опишите вашу проблему <u>одним сообщением</u>. Админ получит его мгновенно и ответит вам здесь же.\n\n"
        "<i>Для выхода в меню просто нажмите любую кнопку внизу.</i>"
    )

@dp.message(UserState.in_support)
async def support_handler(message: Message):
    if message.text in ["💎 Оформить подписку", "📊 Мой статус", "🆘 Техподдержка", "⚙️ Админ-Центр"]: return
    await bot.send_message(
        ADMIN_ID, 
        f"<b>📟 СООБЩЕНИЕ В ПОДДЕРЖКУ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 От: {message.from_user.mention_html()}\n"
        f"🆔 ID: <code>{message.from_user.id}</code>\n\n"
        f"💬 Текст: <i>{message.text}</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>(Ответьте на это сообщение, чтобы отправить ответ пользователю)</i>"
