import asyncpg
import os

pool = None

async def init():
    global pool
    pool = await asyncpg.create_pool(os.getenv("DATABASE_URL"))

    async with pool.acquire() as conn:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS users(
            user_id BIGINT PRIMARY KEY,
            expire BIGINT DEFAULT 0,
            banned INT DEFAULT 0
        )
        """)


async def fetch_user(uid):
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", uid)


async def exec(query, *args):
    async with pool.acquire() as conn:
        return await conn.execute(query, *args)
