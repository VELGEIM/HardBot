from datetime import datetime

def status(u):
    now = int(datetime.now().timestamp())
    if not u:
        return "🔴 NO DATA"

    if u["expire"] > now:
        d = (u["expire"] - now)//86400
        return f"🟢 ACTIVE\n⏳ {d} DAYS LEFT"
    return "🔴 EXPIRED"


def home(user):
    return f"""
🧠 HARDHUB CONTROL PANEL

👤 USER: @{user.username or 'user'}
📊 STATUS: {status(user)}

━━━━━━━━━━━━━━
⚡ CRM SYSTEM ACTIVE
🔐 ANTI-SHARE PROTECTION ON
📡 SUPPORT RADIO ENABLED
━━━━━━━━━━━━━━
"""


def store():
    return """
💎 HARDHUB STORE

Choose your access:

🟣 1 MONTH — 500₽
🟢 6 MONTH — 2450₽
🔵 12 MONTH — 5500₽

⚡ instant unlock
🔐 1 user = 1 link
"""


def profile_card(user, is_active):
    return f"""
👤 USER CARD

ID: {user['user_id']}
NAME: @{user['username']}

STATUS: {"🟢 ACTIVE" if is_active else "🔴 BLOCKED"}

━━━━━━━━━━━━━━
💰 PAID: {user.get('rub_paid',0)}₽
📦 SUB: {user.get('expire',0)}
━━━━━━━━━━━━━━
"""


def admin_dashboard(total, active, income):
    return f"""
⚙️ CRM DASHBOARD

👥 USERS: {total}
🟢 ACTIVE: {active}
💰 INCOME: {income}₽

━━━━━━━━━━━━━━
📡 SYSTEM ONLINE
"""
