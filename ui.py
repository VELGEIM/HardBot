from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


def main_kb(uid, is_admin=False):
    kb = [
        [KeyboardButton(text="💎 Купить доступ")],
        [KeyboardButton(text="📊 Профиль")]
    ]
    if is_admin:
        kb.append([KeyboardButton(text="⚙️ CRM")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def shop():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 месяц - 500₽", callback_data="buy:1m")],
        [InlineKeyboardButton(text="6 месяцев - 2450₽", callback_data="buy:6m")],
        [InlineKeyboardButton(text="12 месяцев - 5500₽", callback_data="buy:12m")]
    ])


def user_card(uid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton("BAN", callback_data=f"ban:{uid}"),
            InlineKeyboardButton("UNBAN", callback_data=f"unban:{uid}")
        ],
        [
            InlineKeyboardButton("RESET", callback_data=f"reset:{uid}")
        ]
    ])
