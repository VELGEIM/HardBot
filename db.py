import asyncpg
import os

pool = None


async def init():
    global pool
    pool = await asyncpg.create_pool(os.getenv("DATABASE_URL"))

    async with pool.acquire() as c:
        await c.execute("""
        CREATE TABLE IF NOT EXISTS users(
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            expire BIGINT DEFAULT 0,
            last_pay BIGINT DEFAULT 0,
            banned INT DEFAULT 0
        )
        """)


async def user(uid):
    async with pool.acquire() as c:
        return await c.fetchrow("SELECT * FROM users WHERE user_id=$1", uid)
