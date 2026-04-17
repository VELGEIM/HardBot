import asyncio

async def loading(msg, base="Загрузка"):
    frames = [
        f"⏳ {base}.",
        f"⏳ {base}..",
        f"⏳ {base}...",
        "🔍 Проверка данных",
        "⚡ Обработка",
        "✨ Готово"
    ]

    for f in frames:
        await asyncio.sleep(0.6)
        try:
            await msg.edit_text(f)
        except:
            pass


async def slide_transition(msg, text):
    frames = [
        "▒▒▒▒▒▒▒▒",
        "▓▒▒▒▒▒▒▒",
        "▓▓▒▒▒▒▒▒",
        "▓▓▓▒▒▒▒▒",
        "▓▓▓▓▒▒▒▒",
        "▓▓▓▓▓▒▒▒",
        "▓▓▓▓▓▓▒▒",
        "▓▓▓▓▓▓▓▒",
        "▓▓▓▓▓▓▓▓",
    ]

    for f in frames:
        await asyncio.sleep(0.2)
        try:
            await msg.edit_text(f"{f}\n\n{text}")
        except:
            pass
