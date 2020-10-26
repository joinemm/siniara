import modules.logger as log

logger = log.get_logger(__name__)


async def get_filter(db):
    data = await db.execute("SELECT DISTINCT twitter_user_id FROM follow")
    return [str(x[0]) for x in data]


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
        "SELECT follow_limit FROM guild WHERE guild_id = %s", guild_id, onerow=True
    )

    current = await db.execute(
        "SELECT COUNT(DISTINCT twitter_user_id) FROM follow WHERE guild_id = %s",
        guild_id,
        onerow=True,
    )
    current = current[0] if current else 0
    return current, limit[0]


async def set_config_guild(db, guild_id, setting, value):
    # just in case, dont allow anything else inside the sql string
    if setting not in ["fansite_format", "ignore_text"]:
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
    if setting not in ["fansite_format", "ignore_text"]:
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
    if setting not in ["fansite_format", "ignore_text"]:
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
    channel_settings = await db.execute(
        "SELECT fansite_format, ignore_text FROM channel_settings WHERE channel_id = %s",
        channel.id,
        onerow=True,
    )
    guild_settings = await db.execute(
        "SELECT fansite_format, ignore_text FROM guild_settings WHERE guild_id = %s",
        channel.guild.id,
        onerow=True,
    )
    user_settings = await db.execute(
        "SELECT fansite_format, ignore_text FROM user_settings WHERE twitter_user_id = %s AND guild_id = %s",
        user_id,
        channel.guild.id,
        onerow=True,
    )
    config = {}

    for i, option in enumerate(["fansite_format", "ignore_text"]):

        if user_settings and user_settings[i] is not None:
            value = user_settings[i]
        elif channel_settings and channel_settings[i] is not None:
            value = channel_settings[i]
        elif guild_settings and guild_settings[i] is not None:
            value = guild_settings[i]
        else:
            value = False

        config[option] = value

    return config
