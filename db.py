import asyncpg
from config import DB_URL

pool: asyncpg.Pool | None = None


async def init_db():
    global pool
    pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=10)

    async with pool.acquire() as conn:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS users(
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            expire BIGINT DEFAULT 0,
            is_banned INT DEFAULT 0,
            rub_paid BIGINT DEFAULT 0,
            stars_paid BIGINT DEFAULT 0,
            last_pay BIGINT DEFAULT 0,
            invite TEXT
        )
        """)


async def get_user(user_id: int):
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM users WHERE user_id=$1",
            user_id
        )


async def execute(query: str, *args):
    async with pool.acquire() as conn:
        return await conn.execute(query, *args)
