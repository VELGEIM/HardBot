from datetime import datetime

def main_menu(name):
    return (
        f"🔥 <b>HARDHUB PREMIUM</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"👋 Привет, <b>{name}</b>\n\n"
        f"📦 Доступ к системе:\n"
        f"• Закрытый контент\n"
        f"• VIP канал\n"
        f"• Поддержка 24/7\n\n"
        f"━━━━━━━━━━━━━━\n"
        f"👇 Выберите действие"
    )
import asyncio

async def loading_animation(bot, chat_id, message_id, base_text="Загрузка"):
    frames = [
        "⏳ Загрузка.",
        "⏳ Загрузка..",
        "⏳ Загрузка...",
        "⚡ Обработка данных",
        "⚡ Проверка платежа",
        "🔄 Финализация"
    ]

    for f in frames:
        try:
            await bot.edit_message_text(
                f"<b>{f}</b>",
                chat_id=chat_id,
                message_id=message_id
            )
            await asyncio.sleep(0.6)
        except:
            pass

def status_text(expire):
    now = int(datetime.now().timestamp())

    if expire > now:
        days = (expire - now) // 86400
        return (
            "🟢 <b>ACTIVE SUBSCRIPTION</b>\n"
            f"⏳ Осталось: <b>{days} дней</b>"
        )

    return "🔴 <b>NO ACTIVE SUBSCRIPTION</b>"


def pay_text(price, card):
    return (
        "💳 <b>PAYMENT REQUIRED</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"💰 Цена: <b>{price}₽</b>\n"
        f"💳 Карта: <code>{card}</code>\n\n"
        "📸 Отправьте <b>ФОТО ЧЕКА</b>\n"
        "━━━━━━━━━━━━━━\n"
        "⚡ Проверка вручную админом"
    )


def admin_panel():
    return "⚙️ <b>ADMIN CRM PANEL</b>"
