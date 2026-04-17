import asyncio
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.types import Update
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

import db
import crm
import ui
from config import TOKEN, PUBLIC_URL, PORT, ADMIN_IDS


bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

dp.include_router(crm.router)

logging.basicConfig(level=logging.INFO)


# ================= START =================
async def on_start(app):
    await db.init_db()

    if not PUBLIC_URL:
        raise RuntimeError("PUBLIC_URL missing")

    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(f"{PUBLIC_URL}/webhook")

    logging.info("BOT READY")


# ================= WEBHOOK =================
async def webhook(request):
    data = await request.json()
    update = Update.model_validate(data)

    await dp.feed_update(bot, update)
    return web.Response(text="OK")


# ================= APP =================
app = web.Application()
app.router.add_post("/webhook", webhook)
app.on_startup.append(on_start)


async def on_shutdown(app):
    await bot.session.close()
    await db.pool.close()


app.on_cleanup.append(on_shutdown)


if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=PORT)
