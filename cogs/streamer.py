import discord
from discord.ext import commands, tasks
from modules import logger as log, menus, database_actions as queries, exceptions
import tweepy
import asyncio
import os
import re
import aiohttp
import arrow
from time import time

logger = log.get_logger(__name__)


class Listener(tweepy.streaming.StreamListener):
    def __init__(self, streamer, filter_array):
        self.streamer = streamer
        self.current_filter = filter_array
        super().__init__()

    def on_connect(self):
        logger.info("Streamer connected!")

    def on_status(self, status):
        self.streamer.bot.loop.create_task(self.streamer.statushandler(status))
        return True

    def on_error(self, status):
        logger.error(status)
        return True

    def on_exception(self, exception):
        logger.error(f"Streamer Error: {exception}")
        return True

    def on_timeout(self):
        logger.error("Stream timed out!")
        return True


class Streamer(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.twitter_stream = None
        self.booted = False
        self.last_connection = 0.0
        self.auth = tweepy.OAuthHandler(
            self.bot.config.twitter_consumer_key, self.bot.config.twitter_consumer_secret
        )
        self.auth.set_access_token(
            self.bot.config.twitter_access_token, self.bot.config.twitter_access_secret
        )
        self.api = tweepy.API(self.auth, wait_on_rate_limit=True)
        self.bot.loop.create_task(self.run_stream())
        self.refresh_loop.start()

    def cog_unload(self):
        self.disconnect_stream()

    def disconnect_stream(self):
        logger.info("Disconnecting Streamer...")
        self.twitter_stream.disconnect()
        del self.twitter_stream
        self.twitter_stream = None

    async def stream_running(self):
        if self.twitter_stream is None:
            return False
        else:
            return self.twitter_stream.running

    @tasks.loop(minutes=5)
    async def refresh_loop(self):
        try:
            await self.check_for_filter_changes()
        except Exception as e:
            logger.error("Unhandled exception in refresh loop")
            logger.error(e)

    @refresh_loop.before_loop
    async def before_refresh_loop(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(60 * 5)  # only start refresh loop 5 minutes after boot up
        logger.info("Starting streamer refresh loop")

    async def check_for_filter_changes(self):
        """Check if new follows have been added to the database and reset stream if so."""
        if self.twitter_stream is None:
            return

        if not await self.stream_running():
            await self.refresh_stream()
        else:
            filter_array = await queries.get_filter(self.bot.db)
            if filter_array != self.twitter_stream.listener.current_filter:
                await self.refresh_stream()

    async def refresh_stream(self):
        """Refresh the twitter stream."""
        if self.twitter_stream is not None:
            self.disconnect_stream()
        logger.warning("Reconnecting streamer...")
        self.bot.loop.create_task(self.run_stream())

    async def run_stream(self):
        """Run the twitter stream in a new thread."""
        await self.bot.wait_until_ready()
        filter_array = await queries.get_filter(self.bot.db)
        while not filter_array:
            await asyncio.sleep(60)
            filter_array = await queries.get_filter(self.bot.db)

        # don't connect more than 1 times per 60 seconds
        if time() - self.last_connection < 60:
            await asyncio.sleep(int(time() - self.last_connection))

        self.twitter_stream = tweepy.Stream(
            self.auth, Listener(self, filter_array), tweet_mode="extended", daemon=True
        )
        await self.update_presence(len(filter_array))
        self.last_connection = time()
        self.twitter_stream.filter(follow=filter_array, is_async=True)

    async def update_presence(self, count):
        """Update the amount of fansites displayed on the bot presence."""
        await self.bot.change_presence(activity=discord.Activity(name=f"{count} Fansites", type=3))

    async def statushandler(self, status):
        """Handle an incoming twitter status."""
        # check if status is posted by one of the followed accounts
        if str(status.user.id) not in self.twitter_stream.listener.current_filter:
            return
        # check if status is a retweet
        if hasattr(status, "retweeted_status"):
            return

        # status is filtered out, get tweet object and send it to channels
        tweet = self.api.get_status(str(status.id), tweet_mode="extended", include_entities=True)
        for channel_id in await queries.get_channels(self.bot.db, tweet.user.id):
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                logger.warning(f"Could not find channel #{channel_id}")
            else:
                await self.send_tweet(channel, tweet)
                logger.info(
                    f"{tweet.id} by @{tweet.user.screen_name} -> #{channel.name} in {channel.guild.name}"
                )

    async def send_tweet(self, channel, tweet):
        """Format and send a tweet to given discord channel."""
        media_files = []
        try:
            media = tweet.extended_entities.get("media", [])
        except AttributeError:
            media = []

        for i in range(len(media)):
            media_type = "image"
            media_url = media[i]["media_url"]
            if not media[i]["type"] == "photo":
                video_urls = media[i]["video_info"]["variants"]
                largest_rate = None
                for x in range(len(video_urls)):
                    if video_urls[x]["content_type"] == "video/mp4":
                        if largest_rate is None or video_urls[x]["bitrate"] > largest_rate:
                            largest_rate = video_urls[x]["bitrate"]
                            media_url = video_urls[x]["url"]
                            media_type = "video"

            media_files.append((media_type, media_url))

        tweet_config = await queries.tweet_config(self.bot.db, channel, tweet.user.id)
        if not media_files and tweet_config["ignore_text"]:
            return

        if not media_files or not tweet_config["fansite_format"]:
            content = discord.Embed(colour=int(tweet.user.profile_link_color, 16))
            content.set_author(
                icon_url=tweet.user.profile_image_url,
                name=f"@{tweet.user.screen_name}",
                url=f"https://twitter.com/{tweet.user.screen_name}/status/{tweet.id}",
            )
            content.description = tweet.full_text

            if media_files:
                first = True
                for file in media_files:
                    if file[0] == "image":
                        content.set_image(url=file[1].replace(".jpg", "?format=jpg&name=orig"))
                        await channel.send(embed=content)
                    else:
                        content._image = None
                        if first:
                            await channel.send(embed=content)
                        await channel.send(file[1])
                    if first:
                        content.description = None
                        content._author = None
                        first = False

            else:
                await channel.send(embed=content)
        else:
            timestamp = arrow.get(tweet.created_at).format("YYMMDD")
            nums = re.findall(r"(\d{6})", tweet.full_text)
            number = ", ".join(nums)
            if number == "":
                # no date specified in post, use posted on date
                number = "*" + str(timestamp)

            tweet_link = tweet.full_text.split(" ")[-1]
            caption = f"```java\n{number} | @{tweet.user.screen_name} | {tweet_link[len('https://'):]}\n```"
            files = []
            # download file and rename, upload to discord
            async with aiohttp.ClientSession() as session:
                timestamp = arrow.get(tweet.created_at).format("YYMMDD")
                for n, (media_type, media_url) in enumerate(media_files, start=1):
                    # is image not video
                    if media_type == "video":
                        extension = "mp4"
                    else:
                        extension = "jpeg"
                        media_url = media_url.replace(".jpg", "?format=jpg&name=orig").replace(
                            ".jpeg", "?format=jpeg&name=orig"
                        )

                    filename = f"{timestamp}-@{tweet.user.screen_name}-{tweet.id}-{n}.{extension}"
                    async with session.get(media_url) as response:
                        with open(filename, "wb") as f:
                            while True:
                                block = await response.content.read(1024)
                                if not block:
                                    break
                                f.write(block)

                    with open(filename, "rb") as f:
                        files.append(discord.File(f))

                    os.remove(filename)

            await channel.send(caption, files=files)

    async def follow(self, channel, user_id, username, timestamp):
        await self.bot.db.execute(
            """
            INSERT INTO twitter_user VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE username = %s
            """,
            user_id,
            username,
            username,
        )
        await self.bot.db.execute(
            "INSERT INTO follow VALUES (%s, %s, %s, %s)",
            channel.id,
            channel.guild.id,
            user_id,
            timestamp,
        )

    async def unfollow(self, channel, user_id):
        await self.bot.db.execute(
            "DELETE FROM follow WHERE twitter_user_id = %s AND channel_id = %s",
            user_id,
            channel.id,
        )

    # COMMANDS

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def add(self, ctx, channel: discord.TextChannel, *usernames):
        """Add users to the follow list."""
        if not usernames:
            raise exceptions.Info("You must give at least one twitter user to follow!")

        rows = []
        time_now = arrow.now().datetime
        current_users = await self.bot.db.execute(
            "SELECT twitter_user_id FROM follow WHERE channel_id = %s", channel.id
        )
        guild_follow_current, guild_follow_limit = await queries.get_follow_limit(
            self.bot.db, channel.guild.id
        )
        successes = 0
        for username in usernames:
            status = None
            try:
                user_id = self.api.get_user(screen_name=username).id
            except tweepy.error.TweepError as e:
                status = f":x: Error {e.args[0][0]['code']}: {e.args[0][0]['message']}"
            else:
                if (user_id,) in current_users:
                    status = ":x: User already being followed on this channel"
                else:
                    if guild_follow_current >= guild_follow_limit:
                        status = f":lock: Guild follow count limit reached ({guild_follow_limit})"
                    else:
                        await self.follow(channel, user_id, username, time_now)
                        status = ":white_check_mark: Success"
                        successes += 1
                        guild_follow_current += 1

            rows.append(f"**@{username}** {status}")

        content = discord.Embed(
            title=f":notepad_spiral: Added {successes}/{len(usernames)} users to {channel.name}",
            color=self.bot.twitter_blue,
        )
        content.set_footer(text="Changes will take effect in the next 5 minutes")
        pages = menus.Menu(source=menus.ListMenu(rows, embed=content), clear_reactions_after=True)
        await pages.start(ctx)

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def addlist(self, ctx, channel: discord.TextChannel, url):
        """Add all users from a twitter list."""
        try:
            list_id = int(url)
        except ValueError:
            regex = r"twitter.com\/i\/lists\/(\d*)"
            match = re.search(regex, url).group(1)
            try:
                list_id = int(match)
            except ValueError:
                raise exceptions.Warning(
                    'Malformed list url! Use list ID or full url such as "https://twitter.com/i/lists/1096201347353985025"'
                )
        users = [
            (u.id, u.screen_name)
            for u in tweepy.Cursor(self.api.list_members, list_id=list_id).items()
        ]
        if not users:
            raise exceptions.Warning("This list is empty!")

        current_users = await self.bot.db.execute(
            "SELECT twitter_user_id FROM follow WHERE channel_id = %s", channel.id
        )
        guild_follow_current, guild_follow_limit = await queries.get_follow_limit(
            self.bot.db, channel.guild.id
        )
        time_now = arrow.now().datetime
        rows = []
        successes = 0
        for user_id, username in users:
            if (user_id,) in current_users:
                status = ":x: User already being followed on this channel"
            else:
                if guild_follow_current >= guild_follow_limit:
                    status = f":lock: Guild follow count limit reached ({guild_follow_limit})"
                else:
                    await self.follow(channel, user_id, username, time_now)
                    status = ":white_check_mark: Success"
                    successes += 1
                    guild_follow_current += 1

            rows.append(f"**@{username}** {status}")

        content = discord.Embed(
            title=f":notepad_spiral: Added {successes}/{len(users)} list members to {channel.name}",
            color=self.bot.twitter_blue,
        )
        content.set_footer(text="Changes will take effect in the next 5 minutes")
        pages = menus.Menu(source=menus.ListMenu(rows, embed=content), clear_reactions_after=True)
        await pages.start(ctx)

    @commands.command(name="del", aliases=["delete", "remove"])
    @commands.has_permissions(manage_guild=True)
    async def remove(self, ctx, channel: discord.TextChannel, *usernames):
        """Remove users from the follow list."""
        if not usernames:
            raise exceptions.Info("You must give at least one twitter user to remove!")

        rows = []
        current_users = await self.bot.db.execute(
            "SELECT twitter_user_id FROM follow WHERE channel_id = %s", channel.id
        )
        successes = 0
        for username in usernames:
            status = None
            try:
                user_id = self.api.get_user(screen_name=username).id
            except tweepy.error.TweepError as e:
                # user not found, maybe changed username
                # try finding username from cache
                user_id = await self.bot.db.execute(
                    "SELECT user_id FROM twitter_user WHERE username = %s", username
                )
                if user_id:
                    user_id = user_id[0][0]
                else:
                    status = f":x: Error {e.args[0][0]['code']}: {e.args[0][0]['message']}"

            if status is None:
                if (user_id,) not in current_users:
                    status = ":x: User is not being followed on this channel"
                else:
                    await self.unfollow(channel, user_id)
                    status = ":white_check_mark: Success"
                    successes += 1

            rows.append(f"**@{username}** {status}")

        content = discord.Embed(
            title=f":notepad_spiral: Removed {successes}/{len(usernames)} users from {channel.name}",
            color=self.bot.twitter_blue,
        )
        content.set_footer(text="Changes will take effect in the next 5 minutes")
        pages = menus.Menu(source=menus.ListMenu(rows, embed=content), clear_reactions_after=True)
        await pages.start(ctx)

    @commands.command(aliases=["removelist", "deletelist"])
    @commands.has_permissions(manage_guild=True)
    async def dellist(self, ctx, channel: discord.TextChannel, url):
        """Add all users from a twitter list."""
        try:
            list_id = int(url)
        except ValueError:
            regex = r"lists\/(\d*)"
            match = re.search(regex, url).group(1)
            try:
                list_id = int(match)
            except ValueError:
                raise exceptions.Warning(
                    'Malformed list url! Use list ID or full url such as "https://twitter.com/i/lists/1096201347353985025"'
                )
        users = [
            (u.id, u.screen_name)
            for u in tweepy.Cursor(self.api.list_members, list_id=list_id).items()
        ]
        if not users:
            raise exceptions.Warning("This list is empty!")

        current_users = await self.bot.db.execute(
            "SELECT twitter_user_id FROM follow WHERE channel_id = %s", channel.id
        )

        rows = []
        successes = 0
        for user_id, username in users:
            if (user_id,) not in current_users:
                status = ":x: User is not being followed on this channel"
            else:
                await self.unfollow(channel, user_id)
                status = ":white_check_mark: Success"
                successes += 1

            rows.append(f"**@{username}** {status}")

        content = discord.Embed(
            title=f":notepad_spiral: Removed {successes}/{len(users)} list members from {channel.name}",
            color=self.bot.twitter_blue,
        )
        content.set_footer(text="Changes will take effect in the next 5 minutes")
        pages = menus.Menu(source=menus.ListMenu(rows, embed=content), clear_reactions_after=True)
        await pages.start(ctx)

    @commands.group()
    @commands.has_permissions(manage_guild=True)
    async def config(self, ctx):
        """
        Configure posting options per guild, channel or user.

        <configtype> is one of [ channel | user | guild ]

        Config hierarchy is as follows:
            1. User settings overwrite everything else.
            2. Channel settings overwrite guild settings.
            2. Guild settings overwrite default settings.
            3. If nothing is set, default options will be used.
        """
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @config.command()
    async def current(self, ctx):
        """Show all the current configurations on this server."""
        channel_settings = await self.bot.db.execute(
            "SELECT channel_id, fansite_format, ignore_text FROM channel_settings WHERE guild_id = %s",
            ctx.guild.id,
        )
        guild_settings = await self.bot.db.execute(
            "SELECT fansite_format, ignore_text FROM guild_settings WHERE guild_id = %s",
            ctx.guild.id,
            onerow=True,
        )
        user_settings = await self.bot.db.execute(
            """
            SELECT twitter_user.username, fansite_format, ignore_text
            FROM user_settings RIGHT OUTER JOIN twitter_user
            ON twitter_user.user_id = user_settings.twitter_user_id
            WHERE guild_id = %s
            """,
            ctx.guild.id,
        )

        content = discord.Embed(title="Current configuration")
        if guild_settings:
            content.add_field(
                name="Guild settings",
                value=""
                + (f"`fansite={guild_settings[0]}`" if guild_settings[0] else "")
                + (f"`ignoretext={guild_settings[1]}`" if guild_settings[1] else ""),
            )
        if channel_settings:
            content.add_field(
                name="Channel settings",
                value="\n".join(
                    f"<#{cid}>"
                    + (f"`fansite={ff}`" if ff != guild_settings[0] else "")
                    + (f"`ignoretext={it}`" if it != guild_settings[1] else "")
                    for cid, ff, it in channel_settings
                ),
            )
        if user_settings:
            content.add_field(
                name="User settings",
                value="\n".join(
                    f"<#{cid}> `fansite={ff}` `ignoretext={it}`" for cid, ff, it in user_settings
                ),
            )
        await ctx.send(embed=content)

    @config.command()
    async def fansiteformat(self, ctx, configtype, *value):
        """Post tweets in fansite formatting eg. 201022 | @hf_dreamcatcher"""
        await self.config_command(ctx, "fansite_format", configtype, *value)

    @config.command()
    async def ignoretext(self, ctx, configtype, *value):
        """Ignore tweets without any media in them."""
        await self.config_command(ctx, "ignore_text", configtype, *value)

    async def config_command(self, ctx, setting, configtype, *value):
        configtype = configtype.lower()

        if configtype == "guild":
            setting_value = to_bool(value[0])
            await queries.set_config_guild(self.bot.db, ctx.guild.id, setting, setting_value)
            await ctx.send(
                f":white_check_mark: `{setting}` for this server is now **{'ON' if setting_value else 'OFF'}**"
            )

        elif configtype == "channel":
            if len(value) < 2:
                raise exceptions.Info(
                    "Missing information! To set channel settings use <channel> <value>"
                )
            try:
                channel = await commands.TextChannelConverter().convert(ctx, value[0])
                if channel.guild != ctx.guild:
                    raise commands.errors.BadArgument()
            except commands.errors.BadArgument:
                raise exceptions.Warning(f'Unable to find channel "{value[0]}"')
            else:
                setting_value = to_bool(value[1])
                await queries.set_config_channel(self.bot.db, channel, setting, setting_value)
                await ctx.send(
                    f":white_check_mark: `{setting}` in {channel.mention} is now **{'ON' if setting_value else 'OFF'}**"
                )

        elif configtype == "user":
            if len(value) < 2:
                raise exceptions.Info(
                    "Missing information! To set user settings use <username> <value>"
                )
            setting_value = to_bool(value[1])
            username = value[0]
            user_id = await self.bot.db.execute(
                """
                SELECT twitter_user.user_id
                FROM follow RIGHT JOIN twitter_user
                ON twitter_user.user_id = follow.twitter_user_id
                WHERE twitter_user.username = %s AND guild_id = %s""",
                username,
                ctx.guild.id,
                onerow=True,
            )
            if not user_id:
                raise exceptions.Info(f"No channel on this server is following **@{username}**")
            await queries.set_config_user(
                self.bot.db, ctx.guild.id, user_id[0], setting, setting_value
            )
            await ctx.send(
                f":white_check_mark: `{setting}` for **@{username}** is now **{'ON' if setting_value else 'OFF'}**"
            )
        else:
            raise exceptions.Info(
                "Unknown configuration type. Use one of [ channel | user | guild ]"
            )

    @commands.command()
    async def get(self, ctx, *tweets):
        """Manually get tweets."""
        try:
            # delete discord automatic embed
            await ctx.message.edit(suppress=True)
        except discord.Forbidden:
            pass

        for tweet_url in tweets:
            if "status" in tweet_url:
                tweet_id = re.search(r"status/(\d+)", tweet_url).group(1)
            else:
                tweet_id = tweet_url

            try:
                tweet = self.api.get_status(tweet_id, tweet_mode="extended")
            except Exception:
                raise exceptions.Warning(f'Could not find tweet "{tweet_url}"')

            await self.send_tweet(ctx.channel, tweet)

    @commands.command()
    @commands.is_owner()
    async def refresh(self, ctx):
        """Manually refresh the twitter stream."""
        await self.refresh_stream()
        await ctx.send(":white_check_mark: Twitter stream refreshed")

    @commands.command()
    async def status(self, ctx):
        """Get the status of the twitter stream."""
        state = (
            self.twitter_stream.running if self.twitter_stream is not None else self.twitter_stream
        )
        await ctx.send(f":point_right: `self.twitter_stream.running = {state}`")


def setup(bot):
    bot.add_cog(Streamer(bot))


def to_bool(s):
    lowered = s.lower()
    if lowered in ("yes", "y", "true", "t", "1", "enable", "on"):
        return True
    elif lowered in ("no", "n", "false", "f", "0", "disable", "off"):
        return False
    else:
        raise exceptions.Warning('Unable to convert "{s}" to boolean value')
