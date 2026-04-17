import asyncpg
import os

pool: asyncpg.Pool | None = None


async def init():
    global pool
    pool = await asyncpg.create_pool(os.getenv("DATABASE_URL"), min_size=1, max_size=5)


def get_pool():
    if pool is None:
        raise RuntimeError("DB pool not initialized")
    return pool


async def fetch_user(uid: int):
    async with get_pool().acquire() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", uid)


async def exec(query: str, *args):
    async with get_pool().acquire() as conn:
        return await conn.execute(query, *args)
