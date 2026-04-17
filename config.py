import os

TOKEN = os.getenv("BOT_TOKEN")
DB_URL = os.getenv("DATABASE_URL")
PUBLIC_URL = os.getenv("PUBLIC_URL")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
PORT = int(os.getenv("PORT", "10000"))

ADMIN_IDS = set(map(int, os.getenv("ADMIN_IDS", "").split(","))) if os.getenv("ADMIN_IDS") else set()
