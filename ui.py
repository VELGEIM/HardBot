def home(name):
    return f"""
🎬 <b>HARDHUB PREMIUM</b>

Привет, <b>{name}</b>

━━━━━━━━━━━━
🔥 VIP Content System
⚡ Instant Access
🛡 Secure CRM Access
━━━━━━━━━━━━

📌 Выберите действие:
"""


def pay():
    return """
💳 <b>PAYMENT SCREEN</b>

💰 Подписка: PREMIUM
📆 Доступ: 30 дней

📸 Отправьте чек для проверки
"""


def dashboard(active, exp):
    return f"""
📊 <b>USER DASHBOARD</b>

Статус: {'🟢 ACTIVE' if active else '🔴 OFF'}
До: {exp}
"""


def loading():
    return ["⏳", "⏳.", "⏳..", "⏳..."]
