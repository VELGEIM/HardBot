import db


async def is_banned(uid: int):
    u = await db.get_user(uid)
    return u and u["is_banned"] == 1
