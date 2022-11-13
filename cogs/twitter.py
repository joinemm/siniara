import re
import typing

import arrow
import discord
from discord import app_commands
from discord.ext import commands

from modules import queries
from modules.siniara import Siniara
from modules.twitter import NoMedia, TwitterRenderer
from modules.ui import Confirm, RowPaginator, SettingsMenu, followup_or_send


class Twitter(commands.Cog):
    def __init__(self, bot):
        self.bot: Siniara = bot
        self.twitter_renderer = TwitterRenderer(self.bot)

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

    @app_commands.command(name="add")
    @app_commands.default_permissions(manage_guild=True)
    async def add(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        usernames: str,
    ):
        """Add users to the follow list."""
        usernames = usernames.split()
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
                user = (await self.bot.tweepy.get_user(username=username)).data
            except Exception as e:
                status = f":x: Error {e}"
            else:
                if (user.id,) in current_users:
                    status = ":x: User already being followed on this channel"
                else:
                    if guild_follow_current >= guild_follow_limit:
                        status = f":lock: Guild follow count limit reached ({guild_follow_limit})"
                    else:
                        await self.follow(channel, user.id, user.username, time_now)
                        status = ":white_check_mark: Success"
                        successes += 1
                        guild_follow_current += 1

            rows.append(f"**@{user.username}** {status}")

        content = discord.Embed(
            title=f":notepad_spiral: Added {successes}/{len(usernames)} users to {channel.name}",
            color=self.bot.twitter_blue,
        )
        content.set_footer(text="Changes will take effect within a minute")
        await RowPaginator(content, rows).run(interaction)

    @app_commands.command(name="remove")
    @app_commands.default_permissions(manage_guild=True)
    async def remove(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        usernames: str,
    ):
        """Remove users from the follow list."""
        usernames = usernames.split()
        rows = []
        current_users = await self.bot.db.execute(
            "SELECT twitter_user_id FROM follow WHERE channel_id = %s", channel.id
        )
        successes = 0
        for username in usernames:
            status = None
            try:
                user_id = (await self.bot.tweepy.get_user(username=username)).data.id
            except Exception as e:
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
        content.set_footer(text="Changes will take effect within a minute")
        await RowPaginator(content, rows).run(interaction)

    @app_commands.command(name="list")
    async def followslist(
        self,
        interaction: discord.Interaction,
        channel: typing.Optional[discord.TextChannel] = None,
    ):
        """List all followed accounts on server or channel"""
        data = await self.bot.db.execute(
            """
            SELECT twitter_user.username, channel_id, added_on
            FROM follow LEFT JOIN twitter_user
            ON twitter_user.user_id = follow.twitter_user_id WHERE follow.guild_id = %s
            """
            + (f" AND channel_id = {channel.id}" if channel is not None else "")
            + " ORDER BY channel_id, added_on DESC",
            interaction.guild_id,
        )
        content = discord.Embed(title="Followed twitter users", color=self.bot.twitter_blue)
        rows = []
        for username, channel_id, added_on in data:
            followed_for = f"<t:{int(added_on.timestamp())}:R>"
            rows.append(
                (f"<#{channel_id}> < " if channel is None else "")
                + f"[@{username}](https://twitter.com/{username}) {followed_for}"
            )

        if not rows:
            rows.append("Nothing yet :(")

        await RowPaginator(content, rows).run(interaction)

    @app_commands.command()
    @app_commands.default_permissions(manage_guild=True)
    async def config(
        self, interaction: discord.Interaction, channel: typing.Optional[discord.TextChannel]
    ):
        """Configure the tweet filtering settings"""
        await SettingsMenu(self.bot).render(interaction)

    rule_group = app_commands.Group(name="rule", description="Add a config rule")

    @rule_group.command(name="channel")
    async def rule_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel, value: bool
    ):
        """If set to True, only tweets with media will be sent to this channel"""
        await queries.add_rule(self.bot.db, interaction.guild_id, "channel", channel.id, value)
        await interaction.response.send_message(
            f":white_check_mark: New rule: {channel.mention} `media only` = **{value}**"
        )

    @rule_group.command(name="user")
    async def rule_user(self, interaction: discord.Interaction, username: str, value: bool):
        """If set to True, only tweets with media will be sent from this twitter account"""
        user_id = await self.bot.db.execute(
            """
            SELECT twitter_user.user_id
            FROM follow RIGHT JOIN twitter_user
            ON twitter_user.user_id = follow.twitter_user_id
            WHERE twitter_user.username = %s AND guild_id = %s""",
            username,
            interaction.guild_id,
            one_value=True,
        )
        if not user_id:
            await interaction.response.send_message(
                f':x: No channel on this server is following "@{username}"', ephemeral=True
            )

        await queries.add_rule(self.bot.db, interaction.guild_id, "user", user_id, value)
        await interaction.response.send_message(
            f":white_check_mark: New rule: **@{username}** `media only` = **{value}**"
        )

    @app_commands.command(name="get")
    @app_commands.describe(tweets="Tweet links or IDs")
    async def get(
        self,
        interaction: discord.Interaction,
        tweets: str,
        channel: typing.Optional[discord.TextChannel] = None,
    ) -> None:
        """Manually get one or more tweets"""
        if channel:
            perms = channel.permissions_for(interaction.user)
            if not perms.send_messages or not perms.embed_links:
                await interaction.response.send_message(
                    f":no_entry: You need to have **Send Messages** and **Embed Links** permissions in {channel} to do that.",
                    ephemeral=True,
                )
                return
        tweet_ids = []
        for tweet in tweets.split():
            try:
                tweet_ids.append(int(tweet))
            except ValueError:
                try:
                    tweet_ids.append(int(re.search(r"status/(\d+)", tweet).group(1)))
                except AttributeError:
                    await interaction.response.send_message(
                        f":x: Invalid tweet: {tweet}", ephemeral=True
                    )
                    return

        results = []
        await interaction.response.defer()
        for tweet_id in tweet_ids:
            try:
                if channel is None:
                    await self.twitter_renderer.send_tweet(
                        tweet_id, [interaction.channel], interaction=interaction
                    )
                else:
                    await self.twitter_renderer.send_tweet(
                        tweet_id, [channel], interaction=interaction
                    )
                    results.append(f":white_check_mark: `{tweet_id}` -> {channel.mention}")
            except NoMedia:
                if channel is None:
                    await followup_or_send(
                        interaction,
                        interaction.extras.get("responded_once", False),
                        embed=discord.Embed(
                            description=f":warning: `{tweet_id}` has no media and `mediaonly=True`"
                        ),
                    )
                    interaction.extras["responded_once"] = True
                else:
                    results.append(f":warning: `{tweet_id}` has no media and `mediaonly=True`")

        if channel:
            await RowPaginator(discord.Embed(), results).run(interaction)

    @commands.command(hidden=True)
    @commands.is_owner()
    async def purge(self, ctx: commands.Context):
        """Remove all follows from unavailable guilds and channels."""
        data = await self.bot.db.execute(
            """
            SELECT channel_id, guild_id, twitter_user_id, username
            FROM follow
            JOIN twitter_user
            ON twitter_user_id=user_id
            """
        )
        actions = []
        guilds_to_delete = []
        channels_to_delete = []
        users_to_delete = []
        twitter_usernames = {}
        usernames_to_change = []
        for channel_id, guild_id, twitter_uid, username in data:
            if self.bot.get_guild(guild_id) is None:
                actions.append(f"Could not find guild with id: [{guild_id}]")
                guilds_to_delete.append(guild_id)
            elif self.bot.get_channel(channel_id) is None:
                actions.append(f"Could not find channel with id: [{channel_id}]")
                channels_to_delete.append(channel_id)
            else:
                twitter_usernames[twitter_uid] = username

        uids = list(twitter_usernames.keys())
        for uids_chunk in [uids[i : i + 100] for i in range(0, len(uids), 100)]:
            userdata = await self.bot.tweepy.get_users(ids=uids_chunk)
            if userdata.errors:
                for error in userdata.errors:
                    actions.append(error["detail"])
                    users_to_delete.append(int(error["value"]))
            if userdata.data:
                for user in userdata.data:
                    if twitter_usernames[user.id] != user.username:
                        actions.append(
                            f"User has changed username from @{twitter_usernames[user.id]} to @{user.username}"
                        )
                        usernames_to_change.append((user.id, user.username))

        if not actions:
            return await ctx.send("There is nothing to do.")

        content = discord.Embed(
            title="Found issues to fix",
            color=self.bot.twitter_blue,
        )
        await RowPaginator(content, actions).run(ctx)
        view = await Confirm("Do you want to continue?").run(ctx)
        await view.wait()
        if view.value:
            if guilds_to_delete:
                await self.bot.db.execute(
                    "DELETE FROM follow WHERE guild_id IN %s", guilds_to_delete
                )
            if channels_to_delete:
                await self.bot.db.execute(
                    "DELETE FROM follow WHERE channel_id IN %s", channels_to_delete
                )
            if users_to_delete:
                await self.bot.db.execute(
                    "DELETE FROM twitter_user WHERE user_id IN %s", users_to_delete
                )
            for uid, new_name in usernames_to_change:
                await self.bot.db.execute(
                    "UPDATE twitter_user SET username = %s WHERE user_id = %s", new_name, uid
                )
            await ctx.send("Purge complete!")


async def setup(bot: Siniara):
    await bot.add_cog(Twitter(bot))
