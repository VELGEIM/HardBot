import asyncpg
from config import DB_URL

pool = None


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


def get_pool():
    if pool is None:
        raise RuntimeError("DB not initialized. Call init_db first.")
    return pool


async def fetchrow(query, *args):
    p = get_pool()
    async with p.acquire() as conn:
        return await conn.fetchrow(query, *args)


async def fetch(query, *args):
    p = get_pool()
    async with p.acquire() as conn:
        return await conn.fetch(query, *args)


async def execute(query, *args):
    p = get_pool()
    async with p.acquire() as conn:
        return await conn.execute(query, *args)
