import asyncpg
import os

pool = None


async def init_db():
    global pool
    pool = await asyncpg.create_pool(os.getenv("DATABASE_URL"))

    async with pool.acquire() as conn:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS users(
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            expire BIGINT DEFAULT 0,
            last_pay BIGINT DEFAULT 0,
            is_banned INT DEFAULT 0
        )
        """)


async def get_user(uid):
    if not pool:
        raise RuntimeError("DB pool not initialized")

    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM users WHERE user_id=$1", uid
        )
