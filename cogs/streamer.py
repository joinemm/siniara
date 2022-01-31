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
        asyncio.ensure_future(self.streamer.statushandler(status), loop=self.streamer.bot.loop)
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
        self.bot.streamer = self
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
        try:
            while not filter_array:
                await asyncio.sleep(60)
                filter_array = await queries.get_filter(self.bot.db)
        except KeyboardInterrupt:
            return

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
        """Update the amount of users displayed on the bot presence."""
        await self.bot.change_presence(activity=discord.Activity(name=f"{count} accounts", type=3))

    async def statushandler(self, status):
        """Handle an incoming twitter status."""
        # check if status is posted by one of the followed accounts
        if str(status.user.id) not in self.twitter_stream.listener.current_filter:
            return
        # check if status is a retweet
        if hasattr(status, "retweeted_status"):
            return

        # status is filtered out, get tweet object and send it to channels
        try:
            tweet = self.api.get_status(
                str(status.id), tweet_mode="extended", include_entities=True
            )
        except tweepy.TweepError:
            logger.warning(f"No status found with ID {status.id}")
            return

        for channel_id in await queries.get_channels(self.bot.db, tweet.user.id):
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                logger.warning(f"Could not find channel #{channel_id} deleting follow")
                await self.unfollow(channel_id, tweet.user.id)
            else:
                await self.send_tweet(channel, tweet)
                logger.info(
                    f"{tweet.id} by @{tweet.user.screen_name} -> #{channel.name} in {channel.guild.name}"
                )

    async def resolve_shortened_urls(self, urls):
        """Expand t.co links to their original urls."""
        results = []
        async with aiohttp.ClientSession() as session:
            for shortened_url in urls:
                async with session.get(shortened_url) as response:
                    results.append((shortened_url, str(response.url)))
        return results

    async def send_tweet(self, channel, tweet, is_manual=False):
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

        if tweet_config["media_only"] and not media_files:
            return

        timestamp = arrow.get(tweet.created_at)
        tweet_text = tweet.full_text
        tweet_link = f"https://twitter.com/i/status/{tweet.id}"

        links = re.findall(r"https?://\S+", tweet.full_text)
        if media_files:
            tweet_text = tweet_text.replace(links.pop(), "")
        if links:
            resolved = await self.resolve_shortened_urls(links)
            for short_link, full_link in resolved:
                tweet_text = tweet_text.replace(short_link, full_link)

        caption = (
            f"<:twitter:937425165241946162> **@{tweet.user.screen_name}**"
            f" <t:{int(timestamp.timestamp())}>"
            f"\n:link: <{tweet_link}>"
        )

        tweet_text = tweet_text.strip()

        if not tweet_config["media_only"] and tweet_text and not is_manual:
            caption += "\n> " + tweet_text.replace("\n", "\n> ")

        files = []
        if media_files:
            # download file and rename, upload to discord
            async with aiohttp.ClientSession() as session:
                for n, (media_type, media_url) in enumerate(media_files, start=1):
                    # is image not video
                    if media_type == "video":
                        extension = "mp4"
                    else:
                        extension = "jpeg"
                        media_url = media_url.replace(".jpg", "?format=jpg&name=orig").replace(
                            ".jpeg", "?format=jpeg&name=orig"
                        )

                    filename = f"{timestamp.format('YYMMDD')}-@{tweet.user.screen_name}-{tweet.id}-{n}.{extension}"
                    too_big = False
                    max_filesize = 8388608  # discord has 8MB file size limit
                    async with session.get(media_url) as response:
                        if (
                            int(response.headers.get("content-length", max_filesize + 1))
                            > max_filesize
                        ):
                            too_big = True
                        else:
                            with open(filename, "wb") as f:
                                while True:
                                    block = await response.content.read(1024)
                                    if not block:
                                        break
                                    f.write(block)

                    if too_big:
                        caption += f"\n{media_url}"
                    else:
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

    async def unfollow(self, channel_id, user_id):
        await self.bot.db.execute(
            "DELETE FROM follow WHERE twitter_user_id = %s AND channel_id = %s",
            user_id,
            channel_id,
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
        content.set_footer(text="Changes will take effect within the next 5 minutes")
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
        content.set_footer(text="Changes will take effect within the next 5 minutes")
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
                    await self.unfollow(channel.id, user_id)
                    status = ":white_check_mark: Success"
                    successes += 1

            rows.append(f"**@{username}** {status}")

        content = discord.Embed(
            title=f":notepad_spiral: Removed {successes}/{len(usernames)} users from {channel.name}",
            color=self.bot.twitter_blue,
        )
        content.set_footer(text="Changes will take effect within the next 5 minutes")
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
                await self.unfollow(channel.id, user_id)
                status = ":white_check_mark: Success"
                successes += 1

            rows.append(f"**@{username}** {status}")

        content = discord.Embed(
            title=f":notepad_spiral: Removed {successes}/{len(users)} list members from {channel.name}",
            color=self.bot.twitter_blue,
        )
        content.set_footer(text="Changes will take effect within the next 5 minutes")
        pages = menus.Menu(source=menus.ListMenu(rows, embed=content), clear_reactions_after=True)
        await pages.start(ctx)

    @commands.command(name="list", aliases=["follows"])
    async def followslist(self, ctx, channel: discord.TextChannel = None):
        """List all followed accounts on server or channel"""
        data = await self.bot.db.execute(
            """
            SELECT twitter_user.username, channel_id, added_on
            FROM follow LEFT JOIN twitter_user
            ON twitter_user.user_id = follow.twitter_user_id WHERE guild_id = %s
            """
            + (f" AND channel_id = {channel.id}" if channel is not None else "")
            + " ORDER BY channel_id, added_on DESC",
            ctx.guild.id,
        )
        content = discord.Embed(title="Followed twitter users", color=self.bot.twitter_blue)
        rows = []
        for username, channel_id, added_on in data:
            rows.append(
                (f"<#{channel_id}> < " if channel is None else "")
                + f"**@{username}** (since {added_on} UTC)"
            )

        if not rows:
            rows.append("Nothing yet :(")

        pages = menus.Menu(source=menus.ListMenu(rows, embed=content), clear_reactions_after=True)
        await pages.start(ctx)

    @commands.group()
    @commands.has_permissions(manage_guild=True)
    async def mediaonly(self, ctx):
        """
        Ignore tweets without any media in them.

        Config hierarchy is as follows:
            1. User settings overwrite everything else.
            2. Channel settings overwrite guild settings.
            2. Guild settings overwrite default settings.
            3. If nothing is set, default option is post everything.
        """
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @mediaonly.command(name="guild")
    async def mediaonly_guild(self, ctx, value: bool):
        """Guild level setting."""
        await queries.set_config_guild(self.bot.db, ctx.guild.id, "media_only", value)
        await ctx.send(f":white_check_mark: Guild setting **Media only** is now **{value}**")

    @mediaonly.command(name="channel")
    async def mediaonly_channel(self, ctx, channel: discord.TextChannel, value: bool):
        """Channel level setting."""
        await queries.set_config_channel(self.bot.db, channel, "media_only", value)
        await ctx.send(
            f":white_check_mark: Channel setting **Media only** is now **{value}** in {channel.mention}"
        )

    @mediaonly.command(name="user")
    async def mediaonly_user(self, ctx, username, value: bool):
        """User level setting."""
        user_id = await self.bot.db.execute(
            """
            SELECT twitter_user.user_id
            FROM follow RIGHT JOIN twitter_user
            ON twitter_user.user_id = follow.twitter_user_id
            WHERE twitter_user.username = %s AND guild_id = %s""",
            username,
            ctx.guild.id,
            one_value=True,
        )
        if not user_id:
            raise exceptions.Info(f'No channel on this server is following "@{username}"')

        await queries.set_config_user(self.bot.db, ctx.guild.id, user_id, "media_only", value)
        await ctx.send(
            f":white_check_mark: User setting **Media only** is now **{value}** for **@{username}**"
        )

    @mediaonly.command(name="clear")
    async def mediaonly_clear(self, ctx):
        """Clear all current config."""
        await queries.clear_config(self.bot.db, ctx.guild)
        await ctx.send(":white_check_mark: Settings cleared")

    @mediaonly.command(name="current")
    async def mediaonly_current(self, ctx):
        """Show the current configuration."""
        channel_settings = await self.bot.db.execute(
            "SELECT channel_id, media_only FROM channel_settings WHERE guild_id = %s",
            ctx.guild.id,
        )
        guild_setting = await self.bot.db.execute(
            "SELECT media_only FROM guild_settings WHERE guild_id = %s",
            ctx.guild.id,
            one_value=True,
        )
        user_settings = await self.bot.db.execute(
            """
            SELECT twitter_user.username, media_only
            FROM user_settings RIGHT OUTER JOIN twitter_user
            ON twitter_user.user_id = user_settings.twitter_user_id
            WHERE guild_id = %s
            """,
            ctx.guild.id,
        )

        content = discord.Embed(title="Current configuration", color=self.bot.twitter_blue)
        content.add_field(
            name="Guild setting",
            value=f"Media only {':white_check_mark:' if guild_setting else ':x:'}",
        )
        if channel_settings:
            content.add_field(
                name="Channel settings",
                value="\n".join(
                    f"<#{cid}> Media only {':white_check_mark:' if val else ':x:'}"
                    for cid, val in channel_settings
                ),
            )
        if user_settings:
            content.add_field(
                name="User settings",
                value="\n".join(
                    f"**@{uname}** Media only {':white_check_mark:' if val else ':x:'}"
                    for uname, val in user_settings
                ),
            )
        await ctx.send(embed=content)

    @commands.command()
    async def get(self, ctx, *tweets):
        """Manually get tweets."""
        try:
            # delete discord automatic embed
            await ctx.message.edit(suppress=True)
        except (discord.Forbidden, discord.NotFound):
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

            await self.send_tweet(ctx.channel, tweet, is_manual=True)

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
