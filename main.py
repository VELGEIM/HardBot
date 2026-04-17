import asyncio
import logging
from aiohttp import web

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, Update
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart

import db
import crm
import ui
from config import *

bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
dp.include_router(crm.router)

logging.basicConfig(level=logging.INFO)


# ================= START =================
@dp.message(CommandStart())
async def start(m: Message):
    await db.fetchrow(
        "INSERT INTO users(user_id, username, first_name) VALUES($1,$2,$3) ON CONFLICT DO NOTHING",
        m.from_user.id, m.from_user.username, m.from_user.first_name
    )

    await m.answer("🔥 HARDHUB ACTIVE", reply_markup=ui.main_kb(m.from_user.id, m.from_user.id in ADMIN_IDS))


# ================= SHOP =================
@dp.message(F.text == "💎 Купить доступ")
async def shop(m: Message):
    await m.answer("💳 Выбор тарифа", reply_markup=ui.shop())


# ================= BUY (ЗАГОТОВКА STARS) =================
@dp.callback_query(F.data.startswith("buy:"))
async def buy(c: CallbackQuery):
    await c.message.edit_text("💳 Оплата через Telegram Stars / manual check позже")


# ================= WEBHOOK =================
async def webhook(request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return web.Response(text="OK")


async def on_start(app):
    await db.init_db()

    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(f"{PUBLIC_URL}/webhook")

    logging.info("BOT READY")


async def on_shutdown(app):
    await bot.session.close()
    if db.pool:
        await db.pool.close()


# ================= APP =================
app = web.Application()
app.router.add_post("/webhook", webhook)

app.on_startup.append(on_start)
app.on_cleanup.append(on_shutdown)


if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=PORT)
