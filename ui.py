from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)


def main_menu(uid: int, is_admin: bool):
    kb = [
        [KeyboardButton(text="💎 Купить доступ")],
        [KeyboardButton(text="📊 Мой профиль")],
        [KeyboardButton(text="🆘 Поддержка")]
    ]

    if is_admin:
        kb.append([KeyboardButton(text="⚙️ CRM Панель")])

    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def shop():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔥 1 месяц — 500₽", callback_data="buy:1m")],
        [InlineKeyboardButton(text="⚡ 6 месяцев — 2450₽", callback_data="buy:6m")],
        [InlineKeyboardButton(text="👑 12 месяцев — 5500₽", callback_data="buy:12m")]
    ])


def user_card(uid, status):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⛔ BAN", callback_data=f"ban:{uid}"),
            InlineKeyboardButton(text="✅ UNBAN", callback_data=f"unban:{uid}")
        ],
        [
            InlineKeyboardButton(text="💣 RESET", callback_data=f"reset:{uid}")
        ],
        [
            InlineKeyboardButton(text="⬅️ BACK", callback_data="adm:users")
        ]
    ])
