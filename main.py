import asyncio
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import aiosqlite
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ---------------- НАСТРОЙКИ ----------------
BOT_TOKEN = "YOUR_BOT_TOKEN"
CHANNEL_ID = -1001234567890
ADMIN_ID = 123456789

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler(timezone="Europe/Berlin")

DB = "/var/data/bot.db"   # ✅ для Render Disk
waiting_for_screen = set()

# ---------------- БАЗА ----------------
async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            expire_date TEXT,
            notified_3 INTEGER DEFAULT 0,
            notified_2 INTEGER DEFAULT 0,
            notified_1 INTEGER DEFAULT 0
        )
        """)
        await db.commit()

async def set_user(user_id, expire_date):
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        INSERT INTO users (user_id, expire_date)
        VALUES (?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET 
            expire_date=excluded.expire_date,
            notified_3=0,
            notified_2=0,
            notified_1=0
        """, (user_id, expire_date))
        await db.commit()

async def get_user(user_id):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(
            "SELECT * FROM users WHERE user_id=?",
            (user_id,)
        )
        return await cur.fetchone()

# ---------------- UI ----------------
def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Купить / Продлить — 500₽", callback_data="buy")],
        [InlineKeyboardButton(text="📦 Моя подписка", callback_data="status")]
    ])

def buy_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 Отправить скрин", callback_data="send_screen")]
    ])

def renew_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Продлить", callback_data="buy")]
    ])

# ---------------- START ----------------
@dp.message(F.text == "/start")
async def start(msg: types.Message):
    await msg.answer(
        "✨ <b>Добро пожаловать!</b>\n\n"
        "📦 Закрытый канал\n"
        "💰 Цена: <b>500₽ / 30 дней</b>",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )

# ---------------- ПОКУПКА ----------------
@dp.callback_query(F.data == "buy")
async def buy(call: types.CallbackQuery):
    await call.message.edit_text(
        "💳 <b>Оплата</b>\n\n"
        "Переведи <b>500₽</b>\n"
        "<code>XXXX-XXXX-XXXX</code>\n\n"
        "После оплаты отправь скрин 👇",
        reply_markup=buy_menu(),
        parse_mode="HTML"
    )

# ---------------- СКРИН ----------------
@dp.callback_query(F.data == "send_screen")
async def send_screen(call: types.CallbackQuery):
    waiting_for_screen.add(call.from_user.id)
    await call.message.answer("📸 Отправь скрин оплаты")

# ---------------- ПОЛУЧЕНИЕ ФОТО ----------------
@dp.message(F.photo)
async def get_photo(msg: types.Message):
    if msg.from_user.id not in waiting_for_screen:
        return

    waiting_for_screen.remove(msg.from_user.id)

    photo = msg.photo[-1].file_id
    user_id = msg.from_user.id

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve_{user_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{user_id}")
        ]
    ])

    await bot.send_photo(
        ADMIN_ID,
        photo,
        caption=f"💰 Новый платёж\n👤 ID: {user_id}",
        reply_markup=kb
    )

    await msg.answer("⏳ Ожидай подтверждения")

# ---------------- ПОДТВЕРЖДЕНИЕ ----------------
@dp.callback_query(F.data.startswith("approve_"))
async def approve(call: types.CallbackQuery):
    user_id = int(call.data.split("_")[1])

    user = await get_user(user_id)

    now = datetime.now()

    if user and user[1]:
        try:
            old_date = datetime.fromisoformat(user[1])
            if old_date > now:
                expire = old_date + timedelta(days=30)
            else:
                expire = now + timedelta(days=30)
        except:
            expire = now + timedelta(days=30)
    else:
        expire = now + timedelta(days=30)

    await set_user(user_id, expire.isoformat())

    invite = await bot.create_chat_invite_link(
        CHANNEL_ID,
        member_limit=1
    )

    await bot.send_message(
        user_id,
        "🎉 <b>Доступ активирован!</b>\n\n"
        f"📅 До: <b>{expire.date()}</b>\n\n"
        f"🔗 {invite.invite_link}",
        reply_markup=renew_menu(),
        parse_mode="HTML"
    )

    await call.message.edit_caption("✅ Подтверждено")

# ---------------- ОТКАЗ ----------------
@dp.callback_query(F.data.startswith("reject_"))
async def reject(call: types.CallbackQuery):
    user_id = int(call.data.split("_")[1])

    await bot.send_message(
        user_id,
        "❌ Платёж не подтверждён",
        reply_markup=renew_menu()
    )

    await call.message.edit_caption("❌ Отклонено")

# ---------------- СТАТУС ----------------
@dp.callback_query(F.data == "status")
async def status(call: types.CallbackQuery):
    user = await get_user(call.from_user.id)

    if not user or not user[1]:
        await call.message.answer("❌ Нет подписки", reply_markup=renew_menu())
        return

    try:
        expire = datetime.fromisoformat(user[1])
    except:
        await call.message.answer("❌ Ошибка данных")
        return

    if datetime.now() > expire:
        await call.message.answer("⛔ Подписка истекла", reply_markup=renew_menu())
    else:
        await call.message.answer(
            f"📦 Активна до: <b>{expire.date()}</b>",
            reply_markup=renew_menu(),
            parse_mode="HTML"
        )

# ---------------- ПРОВЕРКА ----------------
async def check_users():
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("SELECT * FROM users")
        users = await cur.fetchall()

    now = datetime.now()

    for user in users:
        user_id, exp, n3, n2, n1 = user

        if not exp:
            continue

        try:
            exp = datetime.fromisoformat(exp)
        except:
            continue

        days = (exp - now).days

        # ❌ истёк
        if now > exp:
            try:
                await bot.ban_chat_member(CHANNEL_ID, user_id)
                await bot.unban_chat_member(CHANNEL_ID, user_id)
            except:
                pass

            await bot.send_message(
                user_id,
                "⛔ Доступ закончился",
                reply_markup=renew_menu()
            )

        # 🔔 уведомления
        elif days <= 3 and n3 == 0:
            await bot.send_message(user_id, "⚠️ Осталось 3 дня")
            async with aiosqlite.connect(DB) as db:
                await db.execute("UPDATE users SET notified_3=1 WHERE user_id=?", (user_id,))
                await db.commit()

        elif days <= 2 and n2 == 0:
            await bot.send_message(user_id, "⚠️ Осталось 2 дня")
            async with aiosqlite.connect(DB) as db:
                await db.execute("UPDATE users SET notified_2=1 WHERE user_id=?", (user_id,))
                await db.commit()

        elif days <= 1 and n1 == 0:
            await bot.send_message(user_id, "🚨 Последний день!")
            async with aiosqlite.connect(DB) as db:
                await db.execute("UPDATE users SET notified_1=1 WHERE user_id=?", (user_id,))
                await db.commit()

# ---------------- ЗАПУСК ----------------
async def main():
    await init_db()

    scheduler.add_job(check_users, "interval", hours=6)
    scheduler.start()

    await dp.start_polling(bot)

# ---------------- ADMIN PANEL ----------------

def is_admin(user_id: int):
    return user_id == ADMIN_ID


@dp.message(F.text == "/admin")
async def admin_panel(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return

    await msg.answer(
        "🛠 <b>АДМИН ПАНЕЛЬ</b>\n\n"
        "/users — список пользователей\n"
        "/adddays user_id days — добавить дни\n"
        "/ban user_id — забанить\n"
        "/unban user_id — разбанить",
        parse_mode="HTML"
    )


@dp.message(F.text == "/users")
async def users_list(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return

    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("SELECT user_id, expire_date FROM users")
        users = await cur.fetchall()

    text = "👥 <b>Пользователи:</b>\n\n"

    for u in users[:30]:  # ограничение
        uid, exp = u

        if not exp:
            status = "❌ нет подписки"
        else:
            try:
                exp_dt = datetime.fromisoformat(exp)
                status = f"📅 {exp_dt.date()}"
            except:
                status = "⚠️ ошибка даты"

        text += f"👤 {uid} — {status}\n"

    await msg.answer(text, parse_mode="HTML")


@dp.message(F.text.startswith("/adddays"))
async def add_days(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return

    try:
        _, user_id, days = msg.text.split()
        user_id = int(user_id)
        days = int(days)
    except:
        await msg.answer("❌ Используй: /adddays user_id days")
        return

    user = await get_user(user_id)
    now = datetime.now()

    if user and user[1]:
        try:
            current = datetime.fromisoformat(user[1])
            if current > now:
                new_exp = current + timedelta(days=days)
            else:
                new_exp = now + timedelta(days=days)
        except:
            new_exp = now + timedelta(days=days)
    else:
        new_exp = now + timedelta(days=days)

    await set_user(user_id, new_exp.isoformat())

    await msg.answer(f"✅ Добавлено {days} дней пользователю {user_id}")


@dp.message(F.text.startswith("/ban"))
async def ban_user(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return

    try:
        _, user_id = msg.text.split()
        user_id = int(user_id)
    except:
        await msg.answer("❌ Используй: /ban user_id")
        return

    try:
        await bot.ban_chat_member(CHANNEL_ID, user_id)
        await msg.answer(f"🚫 Пользователь {user_id} забанен")
    except:
        await msg.answer("❌ Ошибка бана")


@dp.message(F.text.startswith("/unban"))
async def unban_user(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return

    try:
        _, user_id = msg.text.split()
        user_id = int(user_id)
    except:
        await msg.answer("❌ Используй: /unban user_id")
        return

    try:
        await bot.unban_chat_member(CHANNEL_ID, user_id)
        await msg.answer(f"✅ Пользователь {user_id} разбанен")
    except:
        await msg.answer("❌ Ошибка разбана")
        
if __name__ == "__main__":
    asyncio.run(main())