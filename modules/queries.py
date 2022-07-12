import modules.logger as log

logger = log.get_logger(__name__)


async def get_filter(db):
    data = await db.execute("SELECT DISTINCT twitter_user_id FROM follow")
    return [str(x[0]) for x in data]


async def get_all_users(db):
    data = await db.execute(
        """
        SELECT DISTINCT username
            FROM follow
            JOIN twitter_user
            ON twitter_user_id=user_id
    """
    )
    return [x[0] for x in data]


async def get_channels(db, twitter_user_id):
    data = await db.execute(
        "SELECT DISTINCT channel_id FROM follow WHERE twitter_user_id = %s", twitter_user_id
    )
    return [x[0] for x in data]


async def unlock_guild(db, guild_id):
    await db.execute(
        "UPDATE guild SET follow_limit = %s WHERE guild_id = %s",
        db.bot.config.guild_unlocked_follow_limit,
        guild_id,
    )


async def get_follow_limit(db, guild_id):
    await db.execute(
        "INSERT INTO guild VALUES (%s, %s) ON DUPLICATE KEY UPDATE guild_id = guild_id",
        guild_id,
        db.bot.config.guild_follow_limit,
    )
    limit = await db.execute(
        "SELECT follow_limit FROM guild WHERE guild_id = %s", guild_id, one_row=True
    )

    current = await db.execute(
        "SELECT COUNT(DISTINCT twitter_user_id) FROM follow WHERE guild_id = %s",
        guild_id,
        one_row=True,
    )
    current = current[0] if current else 0
    return current, limit[0]


async def set_config_guild(db, guild_id, setting, value):
    # just in case, dont allow anything else inside the sql string
    if setting not in ["media_only"]:
        logger.error(f"Ignored configtype {setting} from executing in the database!")
    else:
        await db.execute(
            "INSERT INTO guild_settings(guild_id, " + setting + ") VALUES (%s, %s) "
            "ON DUPLICATE KEY UPDATE " + setting + " = %s",
            guild_id,
            value,
            value,
        )


async def set_config_channel(db, channel, setting, value):
    # just in case, dont allow anything else inside the sql string
    if setting not in ["media_only"]:
        logger.error(f"Ignored configtype {setting} from executing in the database!")
    else:
        await db.execute(
            "INSERT INTO channel_settings(channel_id, guild_id, "
            + setting
            + ") VALUES (%s, %s, %s) "
            "ON DUPLICATE KEY UPDATE " + setting + " = %s",
            channel.id,
            channel.guild.id,
            value,
            value,
        )


async def set_config_user(db, guild_id, user_id, setting, value):
    # just in case, dont allow anything else inside the sql string
    if setting not in ["media_only"]:
        logger.error(f"Ignored configtype {setting} from executing in the database!")
    else:
        await db.execute(
            "INSERT INTO user_settings(guild_id, twitter_user_id, "
            + setting
            + ") VALUES (%s, %s, %s) "
            "ON DUPLICATE KEY UPDATE " + setting + " = %s",
            guild_id,
            user_id,
            value,
            value,
        )


async def tweet_config(db, channel, user_id):
    channel_setting = await db.execute(
        "SELECT media_only FROM channel_settings WHERE channel_id = %s",
        channel.id,
        one_value=True,
    )
    guild_setting = await db.execute(
        "SELECT media_only FROM guild_settings WHERE guild_id = %s",
        channel.guild.id,
        one_value=True,
    )
    user_setting = await db.execute(
        "SELECT media_only FROM user_settings WHERE twitter_user_id = %s AND guild_id = %s",
        user_id,
        channel.guild.id,
        one_value=True,
    )
    config = {}

    if user_setting in (True, False):
        value = user_setting
    elif channel_setting in (True, False):
        value = channel_setting
    elif guild_setting in (True, False):
        value = guild_setting
    else:
        value = False

    config["media_only"] = value

    return config


async def clear_config(db, guild):
    await db.execute("DELETE FROM channel_settings WHERE guild_id = %s", guild.id)
    await db.execute("DELETE FROM user_settings WHERE guild_id = %s", guild.id)
    await db.execute("DELETE FROM guild_settings WHERE guild_id = %s", guild.id)
