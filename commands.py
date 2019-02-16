# Project: Joinemm-Bot
# File: commands.py
# Author: Joinemm
# Date created: 03/02/19
# Python Version: 3.6

import discord
from discord.ext import commands
import logger
import utils
import main

log = logger.create_logger(__name__)


class Commands:

    def __init__(self, client):
        self.client = client

    @commands.command()
    async def info(self, ctx):
        """Get information about the bot."""
        log.info(logger.command_log(ctx))

        appinfo = await self.client.application_info()
        info_embed = discord.Embed(title='Fansite Tracker Bot',
                                   description=f'This is a bot for tracking fansites on twitter.\n'
                                   f'use the help command for a list of commands.\n\n'
                                   f'Currently tracking {len(utils.get_follow_ids())} accounts '
                                   f'across {len(self.client.guilds)} servers.\n\n'
                                   f'Author: {appinfo.owner.mention}',
                                   colour=ctx.guild.get_member(self.client.user.id).color)
        info_embed.add_field(name='Patreon', value="https://www.patreon.com/joinemm", inline=False)
        info_embed.set_footer(text='version 3.0')
        info_embed.set_thumbnail(url=self.client.user.avatar_url)
        await ctx.send(embed=info_embed)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def config(self, ctx, param1=None, param2=None, param3=None):
        """Configure bot options."""
        log.info(logger.command_log(ctx))

        if param1 == "help" or param1 is None:
            await ctx.send("`$config [channel] [setting] [True | False]`\n"
                           "**settings:** `[textposts | imagetext | fansiteformatting]`\n")
            return
        else:
            channel = utils.channel_from_mention(ctx.guild, param1)
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
            await ctx.send(f"Set textpost mode for {channel.mention} to `{param3.lower()}`")

        elif param2 == "imagetext":
            if param3.lower() == "true":
                main.database.set_attr("config", f"channels.{channel.id}.include_text", True)
            elif param3.lower() == "false":
                main.database.set_attr("config", f"channels.{channel.id}.include_text", False)
            else:
                await ctx.send(f"ERROR: Invalid parameter `{param3}`. Use `true` or `false`")
                return
            await ctx.send(f"Set imagetext mode for {channel.mention} to `{param3.lower()}`")

        elif param2 == "fansiteformatting":
            if param3.lower() == "true":
                main.database.set_attr("config", f"channels.{channel.id}.format", True)
            elif param3.lower() == "false":
                main.database.set_attr("config", f"channels.{channel.id}.format", False)
            else:
                await ctx.send(f"ERROR: Invalid parameter `{param3}`. Use `true` or `false`")
                return
            await ctx.send(f"Set fansite formatting mode for {channel.mention} to `{param3.lower()}`")

        else:
            settings = main.database.get_attr("config", f"channels.{channel.id}")
            await ctx.send(f"Current settings for {channel.mention}\n```{settings}```")

    @commands.command()
    async def list(self, ctx, mention=None):
        """List the currently followed accounts on this server."""
        log.info(logger.command_log(ctx))

        channel_limit = None
        if mention is not None:
            channel_limit = utils.channel_from_mention(ctx.guild, mention)
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
            await utils.page_switcher(self.client, msg, content, pages)


def setup(client):
    client.add_cog(Commands(client))
