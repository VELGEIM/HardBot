import asyncio
import os
import datetime
import logging

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.types import *
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart

import db
import ui
import fx

# ================= CHECK ENV =================
if not os.getenv("BOT_TOKEN"):
    raise RuntimeError("BOT_TOKEN missing")

# ================= INIT =================
TOKEN = os.getenv("BOT_TOKEN")
PUBLIC_URL = os.getenv("PUBLIC_URL")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

ADMINS = set(map(int, os.getenv("ADMIN_IDS", "").split(",")))

bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


# ================= START =================
@dp.message(CommandStart())
async def start(m: Message):
    await db.upsert_user(
        m.from_user.id,
        m.from_user.username,
        m.from_user.first_name
    )

    await m.answer(ui.home(m.from_user.first_name))


# ================= STATUS =================
@dp.message(F.text == "📊 Статус")
async def status(m: Message):
    u = await db.get_user(m.from_user.id)
    now = int(datetime.datetime.now().timestamp())

    if u and u["expire"] > now:
        await m.answer(ui.status(True, u["expire"]))
    else:
        await m.answer(ui.status(False, 0))


# ================= BUY =================
@dp.message(F.text == "💎 Купить")
async def buy(m: Message):
    await m.answer(ui.pay())


# ================= PHOTO CHECK =================
@dp.message(F.photo)
async def photo(m: Message):
    msg = await m.answer("⏳ processing...")

    await fx.loading(msg)

    for a in ADMINS:
        await bot.send_photo(
            a,
            m.photo[-1].file_id,
            caption=f"CHECK {m.from_user.id}"
        )


# ================= APPROVE =================
@dp.callback_query(F.data.startswith("ok:"))
async def ok(c: CallbackQuery):
    uid = int(c.data.split(":")[1])

    exp = int(datetime.datetime.now().timestamp()) + 30 * 86400

    await db.execute(
        "UPDATE users SET expire=$1 WHERE user_id=$2",
        exp, uid
    )

    link = await bot.create_chat_invite_link(
        CHANNEL_ID,
        member_limit=1
    )

    await bot.send_message(uid, f"🔥 ACCESS GRANTED\n{link.invite_link}")


# ================= WEBHOOK =================
async def webhook(r):
    data = await r.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return web.Response(text="OK")


async def on_start(app):
    await db.init_db()
    await bot.set_webhook(f"{PUBLIC_URL}/webhook")
    print("BOT ONLINE")


app = web.Application()
app.router.add_post("/webhook", webhook)
app.on_startup.append(on_start)


if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
