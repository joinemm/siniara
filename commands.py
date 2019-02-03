# Project: Joinemm-Bot
# File: commands.py
# Author: Joinemm
# Date created: 02/02/19
# Python Version: 3.6

import discord
from discord.ext import commands
import logger
import time
import main
import asyncio

log = logger.create_logger(__name__)


class Commands:

    def __init__(self, client):
        self.client = client
        self.start_time = time.time()

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def add(self, ctx, mention, *usernames):
        """Add an account to the follow list"""
        log.info(logger.command_log(ctx))

        channel = channel_from_mention(ctx.guild, mention)
        if channel is None:
            await ctx.send("Invalid channel")
            return
        for username in usernames:
            response = main.add_fansite(username, channel.id)
            if response is True:
                await ctx.send(f"Added `{username}` to {channel.mention}")
            else:
                await ctx.send(f"Error adding `{username}`: `{response}`")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def remove(self, ctx, mention, *usernames):
        """Remove an account from the follow list"""
        log.info(logger.command_log(ctx))

        channel = channel_from_mention(ctx.guild, mention)
        if channel is None:
            await ctx.send("Invalid channel")
            return
        for username in usernames:
            response = main.remove_fansite(username, channel.id)
            if response is True:
                await ctx.send(f"Removed `{username}` from {channel.mention}")
            else:
                await ctx.send(f"Error removing `{username}`: `{response}`")

    @commands.command()
    @commands.cooldown(1, 60)
    @commands.has_permissions(administrator=True)
    async def reset(self, ctx):
        """Reset the stream; refresh follows and settings"""
        log.info(logger.command_log(ctx))

        main.stream.refresh()
        await ctx.send("TwitterStream reinitialized, follow list updated")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def config(self, ctx, param1=None, param2=None, param3=None):
        """Configure bot options."""
        log.info(logger.command_log(ctx))

        if param1 == "help" or param1 is None:
            await ctx.send("`$config [channel] [setting] [True | False]`\n"
                           "**settings:** `[textposts | imagetext]`\n")
            return
        else:
            channel = channel_from_mention(ctx.guild, param1)
            if channel is None:
                await ctx.send("Invalid channel")

        if param2 == "textposts":
            if param3.lower() == "true":
                main.database.set_attr("config", f"channels.{channel.id}.text_posts", True)
            elif param3.lower() == "false":
                main.database.set_attr("config", f"channels.{channel.id}.text_posts", False)
            else:
                await ctx.send(f"ERROR: Invalid parameter `{param3}`. Use `true` or `false`")
                return
        elif param2 == "imagetext":
            if param3.lower() == "true":
                main.database.set_attr("config", f"channels.{channel.id}.include_text", True)
            elif param3.lower() == "false":
                main.database.set_attr("config", f"channels.{channel.id}.include_text", False)
            else:
                await ctx.send(f"ERROR: Invalid parameter `{param3}`. Use `true` or `false`")
                return
        else:
            settings = main.database.get_attr("config", f"channels.{channel.id}")
            await ctx.send(f"Current settings for {channel.mention}\n```{settings}```")

    @commands.command()
    async def list(self, ctx, mention=None):
        """List the currently followed accounts on this server."""
        log.info(logger.command_log(ctx))

        channel_limit = None
        if mention is not None:
            channel_limit = channel_from_mention(ctx.guild, mention)
            if channel_limit is None:
                await ctx.send(f"Invalid channel `{mention}`")
                return

        followlist = main.database.get_attr("follows", ".")

        pages = []
        rows = []
        for userid in followlist:
            channel_mentions = []
            for channel_id in followlist[userid]['channels']:
                channel = ctx.guild.get_channel(channel_id)
                if channel is not None:
                    if channel_limit is not None and not channel == channel_limit:
                        continue
                    channel_mentions.append(channel.mention)

            if channel_mentions:
                username = main.database.get_attr("follows", f"{userid}.username", "ERROR")
                text_posts = main.database.get_attr("follows", f"{userid}.text_posts", 0)
                images = main.database.get_attr("follows", f"{userid}.images", 0)
                if channel_limit is not None:
                    rows.append(f"**{username}** ({text_posts}|{images})")
                else:
                    rows.append(f"**{username}** ({text_posts}|{images}) >> {'|'.join(channel_mentions)}")
            if len(rows) == 25:
                pages.append("\n".join(rows))
                rows = []

        if rows:
            pages.append("\n".join(rows))

        if not pages:
            await ctx.send("I am not following any users on this server yet!")
            return

        content = discord.Embed()
        if channel_limit is not None:
            content.title = f"Followed users in **{channel_limit.name}** channel | (text|image) posts:"
        else:
            content.title = f"Followed users in **{ctx.guild.name}** | (text|image) posts:"

        content.set_footer(text=f"page 1 of {len(pages)}")
        content.description = pages[0]
        msg = await ctx.send(embed=content)

        if len(pages) > 1:
            await self.page_switcher(msg, content, pages)

    @commands.command()
    async def status(self, ctx):
        """Get the bot's status"""
        log.info(logger.command_log(ctx))

        up_time = time.time() - self.start_time
        m, s = divmod(up_time, 60)
        h, m = divmod(m, 60)
        d, h = divmod(h, 24)

        bot_msg = await ctx.send(f"```running = {main.stream.get_status()}\n"
                                 f"heartbeat = {self.client.latency * 1000:.0f}ms\n"
                                 f"roundtrip latency = PENDINGms\n"
                                 f"uptime = {d:.0f} days {h:.0f} hours {m:.0f} minutes {s:.0f} seconds```")

        latency = (bot_msg.created_at - ctx.message.created_at).total_seconds() * 1000
        await bot_msg.edit(content=bot_msg.content.replace("PENDING", str(latency)))

    @commands.command()
    async def info(self, ctx):
        """Get information about the bot."""
        log.info(logger.command_log(ctx))

        appinfo = await self.client.application_info()
        info_embed = discord.Embed(title='Fansite Tracker Bot',
                                   description=f'This is a bot for tracking fansites on twitter.\n'
                                   f'use the help command for a list of commands.\n\n'
                                   f'Currently tracking {len(main.get_follow_ids())} accounts '
                                   f'across {len(self.client.guilds)} servers.\n\n'
                                   f'Author: {appinfo.owner.mention}',
                                   colour=ctx.guild.get_member(self.client.user.id).color)
        info_embed.add_field(name='Patreon', value="https://www.patreon.com/joinemm", inline=False)
        info_embed.set_footer(text='version 2.0')
        info_embed.set_thumbnail(url=self.client.user.avatar_url)
        await ctx.send(embed=info_embed)

    async def page_switcher(self, my_msg, content, pages):
        current_page = 0

        def check(_reaction, _user):
            return _reaction.message.id == my_msg.id and _reaction.emoji in ["⬅", "➡"] \
                   and not _user == self.client.user

        await my_msg.add_reaction("⬅")
        await my_msg.add_reaction("➡")

        while True:
            try:
                reaction, user = await self.client.wait_for('reaction_add', timeout=3600.0, check=check)
            except asyncio.TimeoutError:
                return
            else:
                try:
                    if reaction.emoji == "⬅" and current_page > 0:
                        content.description = pages[current_page - 1]
                        current_page -= 1
                        await my_msg.remove_reaction("⬅", user)
                    elif reaction.emoji == "➡":
                        content.description = pages[current_page + 1]
                        current_page += 1
                        await my_msg.remove_reaction("➡", user)
                    else:
                        continue
                    content.set_footer(text=f"page {current_page + 1} of {len(pages)}")
                    await my_msg.edit(embed=content)
                except IndexError:
                    continue


def channel_from_mention(guild, text, default=None):
    text = text.strip("<>#!@")
    try:
        channel = guild.get_channel(int(text))
        if channel is None:
            return default
        return channel
    except ValueError:
        return default

def setup(client):
    client.add_cog(Commands(client))
