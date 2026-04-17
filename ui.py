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
