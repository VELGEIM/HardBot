import asyncpg
import os

DATABASE_URL = os.getenv("DATABASE_URL")

pool: asyncpg.Pool | None = None


async def init_db():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)

    async with pool.acquire() as conn:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS users(
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            expire BIGINT DEFAULT 0,
            is_banned INT DEFAULT 0,
            last_pay BIGINT DEFAULT 0
        )
        """)


async def get_user(uid: int):
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM users WHERE user_id=$1",
            uid
        )


async def upsert_user(uid, username, first_name):
    async with pool.acquire() as conn:
        await conn.execute("""
        INSERT INTO users(user_id, username, first_name)
        VALUES($1,$2,$3)
        ON CONFLICT(user_id) DO UPDATE
        SET username=$2, first_name=$3
        """, uid, username, first_name)
