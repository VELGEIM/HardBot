import asyncio


def main_ui(name):
    return (
        f"🔥 <b>HARDHUB PREMIUM</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"👋 Привет, <b>{name}</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"💎 VIP система доступа\n"
        f"⚡ Авто-выдача подписки\n"
        f"📡 Поддержка 24/7\n"
    )


def status_ui(exp):
    return f"🟢 ACTIVE\n⏳ до: {exp}" if exp else "🔴 NO ACCESS"


async def loading(bot, chat_id, msg_id):
    frames = [
        "⏳ Загрузка.",
        "⏳ Загрузка..",
        "⏳ Загрузка...",
        "⚡ Проверка",
        "🔄 Обработка",
        "🚀 Готово"
    ]

    for f in frames:
        try:
            await bot.edit_message_text(f"<b>{f}</b>", chat_id, msg_id)
            await asyncio.sleep(0.5)
        except:
            pass
