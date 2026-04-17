from datetime import datetime

PRICE = 500
DAYS = 30


def home(name):
    return f"""
🎬 <b>HARDHUB SAAS PANEL</b>

Привет, <b>{name}</b>

━━━━━━━━━━━━━━
🔥 VIP Content System
⚡ Instant Access
🛡 Secure Access Layer
━━━━━━━━━━━━━━

Выберите действие 👇
"""


def status(active, exp):
    if active:
        return f"""
🟢 <b>ACTIVE</b>

⏳ До: <b>{datetime.fromtimestamp(exp).strftime('%d.%m.%Y')}</b>
"""
    return "🔴 <b>NO SUBSCRIPTION</b>"


def pay():
    return f"""
💳 <b>PAYMENT</b>

💰 Цена: {PRICE}₽
📆 Дней: {DAYS}

📸 Отправьте чек (фото)
"""


def anim():
    return [
        "⏳ проверка",
        "⏳ проверка.",
        "⏳ проверка..",
        "⏳ проверка...",
        "🔍 анализ",
        "✅ готово"
    ]
