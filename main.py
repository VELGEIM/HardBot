import asyncio
from aiohttp import web

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

import db
import ui
import crm
import security

TOKEN = os.getenv("BOT_TOKEN")
PUBLIC_URL = os.getenv("PUBLIC_URL")
PORT = int(os.getenv("PORT", 10000))

bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# 🔥 важно: импорт модулей РЕГИСТРИРУЕТ хендлеры
import ui
import crm
import security


async def on_start(app):
    await db.init()

    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(f"{PUBLIC_URL}/webhook")

    print("HARDHUB PRO RUNNING")


async def webhook(request):
    data = await request.json()
    update = types.Update.model_validate(data)
    await dp.feed_update(bot, update)
    return web.Response(text="OK")


app = web.Application()
app.router.add_post("/webhook", webhook)
app.on_startup.append(on_start)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=PORT)
