import time

user_last_action = {}


def can_action(user_id: int) -> bool:
    now = time.time()

    if user_id in user_last_action:
        if now - user_last_action[user_id] < 3:
            return False

    user_last_action[user_id] = now
    return True
