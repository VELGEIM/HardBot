import asyncpg
from datetime import datetime

pool = None


async def get_user(uid):
    async with pool.acquire() as c:
        return await c.fetchrow("SELECT * FROM users WHERE user_id=$1", uid)


async def ban_user(uid):
    async with pool.acquire() as c:
        await c.execute("UPDATE users SET is_banned=1 WHERE user_id=$1", uid)


async def unban_user(uid):
    async with pool.acquire() as c:
        await c.execute("UPDATE users SET is_banned=0 WHERE user_id=$1", uid)


async def reset_user(uid):
    async with pool.acquire() as c:
        await c.execute("UPDATE users SET expire=0 WHERE user_id=$1", uid)
