import time
import db

cache = {}

def check_user(uid):
    now = time.time()

    if uid in cache:
        if now - cache[uid] < 5:
            return False

    cache[uid] = now
    return True
