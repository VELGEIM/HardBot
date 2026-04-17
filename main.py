import asyncio
import os
import datetime
import logging
if not os.getenv("BOT_TOKEN"):
    raise RuntimeError("❌ BOT_TOKEN is not set in environment variables")

if not os.getenv("DATABASE_URL"):
    raise RuntimeError("❌ DATABASE_URL is not set")

if not os.getenv("PUBLIC_URL"):
    raise RuntimeError("❌ PUBLIC_URL is not set")
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.types import *
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

import db
import ui
import fx
import crm

TOKEN = os.getenv("BOT_TOKEN")
URL = os.getenv("PUBLIC_URL")
CHANNEL = int(os.getenv("CHANNEL_ID"))
PORT = int(os.getenv("PORT", 10000))

ADMINS = set(map(int, os.getenv("ADMIN_IDS", "").split(",")))

bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


# ================= START =================
@dp.message(CommandStart())
async def start(m: Message):
    await db.user(m.from_user.id)  # create check
    await m.answer(ui.home(m.from_user.first_name))


# ================= DASH =================
@dp.message(F.text == "📊 Статус")
async def status(m: Message):
    u = await db.user(m.from_user.id)
    now = int(datetime.datetime.now().timestamp())

    if u and u["expire"] > now:
        await m.answer(ui.dashboard(True, u["expire"]))
    else:
        await m.answer(ui.dashboard(False, "—"))


# ================= BUY =================
@dp.message(F.text == "💎 Купить")
async def buy(m: Message):
    msg = await m.answer(ui.pay())

    await fx.slide_transition(msg, "Переход в оплату")


# ================= PHOTO CHECK =================
@dp.message(F.photo)
async def photo(m: Message):
    msg = await m.answer("⏳ Обработка чека...")

    await fx.loading(msg, "Проверка платежа")

    for a in ADMINS:
        await bot.send_photo(a, m.photo[-1].file_id,
            caption=f"CHECK: {m.from_user.id}")


# ================= APPROVE =================
@dp.callback_query(F.data.startswith("ok:"))
async def ok(c: CallbackQuery):
    uid = int(c.data.split(":")[1])
    exp = int(datetime.datetime.now().timestamp()) + 30*86400

    async with db.pool.acquire() as conn:
        await conn.execute("UPDATE users SET expire=$1 WHERE user_id=$2", exp, uid)

    link = await bot.create_chat_invite_link(CHANNEL, member_limit=1)

    await bot.send_message(uid, f"🔥 ACCESS GRANTED\n{link.invite_link}")


# ================= WEBHOOK =================
async def webhook(r):
    data = await r.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return web.Response()


async def start_app(app):
    await db.init()
    await bot.set_webhook(f"{URL}/webhook")


app = web.Application()
app.router.add_post("/webhook", webhook)
app.on_startup.append(start_app)


if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=PORT)
