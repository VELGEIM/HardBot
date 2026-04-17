async def revoke_old_links(bot, channel_id, uid):
    try:
        await bot.create_chat_invite_link(
            channel_id,
            member_limit=1,
            name=f"user_{uid}_new"
        )
    except:
        pass
