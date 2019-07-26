# Project: Fansite Bot
# File: commands.py
# Author: Joinemm
# Date created: 06/04/19
# Python Version: 3.6

import discord
from discord.ext import commands
import utils
import database as db
import arrow
import requests
import json
import copy


class Commands(commands.Cog):

    def __init__(self, client):
        self.client = client

    @commands.command()
    async def info(self, ctx):
        """Get information about the bot."""
        appinfo = await self.client.application_info()
        membercount = len(set(self.client.get_all_members()))
        content = discord.Embed(title=f"Fansite Bot | version 3.5", colour=discord.Color.blue())
        content.description = (f"Created by {appinfo.owner.mention}\n\n"
                              f'This is a bot mainly made for tracking kpop fansites on twitter, but it works '
                              f'just fine for any twitter accounts.\n'
                              f'use `{self.client.command_prefix}help` for the list of commands.\n\n'
                              f'Currently following **{len(db.get_user_ids())}** accounts '
                              f'across **{len(self.client.guilds)}** servers totaling {membercount} unique members')
        content.add_field(name='Github', value='https://github.com/joinemm/fansite-bot', inline=False)
        content.add_field(name='Patreon', value="https://www.patreon.com/joinemm", inline=False)
        content.set_thumbnail(url=self.client.user.avatar_url)
        await ctx.send(embed=content)

    @commands.command()
    async def ping(self, ctx):
        """Get the bot's ping"""
        pong_msg = await ctx.send(":ping_pong:")
        sr_lat = (pong_msg.created_at - ctx.message.created_at).total_seconds() * 1000
        await pong_msg.edit(content=f"Command latency = `{sr_lat}`ms\n"
                                    f"Discord latency = `{self.client.latency * 1000:.1f}`ms")

    @commands.command()
    async def changelog(self, ctx):
        """Get the github commit history"""
        author = "joinemm"
        repo = "fansite-bot"
        data = get_commits(author, repo)
        content = discord.Embed(color=discord.Color.from_rgb(46, 188, 79))
        content.set_author(name="Github commit history", icon_url=data[0]['author']['avatar_url'],
                           url=f"https://github.com/{author}/{repo}/commits/master")
        content.set_thumbnail(url='http://www.logospng.com/images/182/github-icon-182553.png')

        pages = []
        i = 0
        for commit in data:
            if i == 5:
                pages.append(content)
                content = copy.deepcopy(content)
                content.clear_fields()
                i = 0
            sha = commit['sha'][:7]
            author = commit['author'].get('login') if commit['author'] else 'UNKNOWN'
            date = commit['commit']['author'].get('date')
            arrow_date = arrow.get(date)
            url = commit['html_url']
            content.add_field(name=f"[`{sha}`] {commit['commit'].get('message')}",
                              value=f"**{author}** committed {arrow_date.humanize()} | [link]({url})",
                              inline=False)
            i += 1
        pages.append(content)
        await utils.page_switcher(ctx, pages)

    @commands.group()
    @commands.has_permissions(administrator=True)
    async def config(self, ctx, channel=None):
        """Configure channel specific options"""
        if channel is None:
            return await ctx.send_help(ctx.command.name)

        this_channel = await utils.get_channel(ctx, channel)
        if this_channel is None:
            return await ctx.send(f"Invalid channel `{channel}`")

        ctx.the_channel = this_channel

        if ctx.invoked_subcommand is None or isinstance(ctx.invoked_subcommand, commands.Group):
            this_channel = await utils.get_channel(ctx, channel)
            if this_channel is None:
                return await ctx.send(f"Invalid channel `{channel}`")

            settings = db.get_channel_settings(this_channel.id)
            await ctx.send(f"**Current settings for** {this_channel.mention}\n```"
                           f"Text only posts : {settings.text_posts == 1}\n"
                           f"Image text : {settings.image_text == 1}\n"
                           f"Images as links : {settings.image_links == 1}```")

    @config.command()
    async def textposts(self, ctx, value):
        """Allow text only tweets?"""
        value = text_to_int_bool(value)
        if value is None:
            return await ctx.send(f"Invalid value `{value}`. Use `true` or `false`")

        db.change_setting(ctx.the_channel.id, 'text_posts', value)
        await ctx.send(f"Textposts in {ctx.the_channel.mention} `{'enabled' if value == 1 else 'disabled'}`")

    @config.command()
    async def imagetext(self, ctx, value):
        """Post tweet text with images?"""
        value = text_to_int_bool(value)
        if value is None:
            return await ctx.send(f"Invalid value `{value}`. Use `true` or `false`")

        db.change_setting(ctx.the_channel.id, 'image_text', value)
        await ctx.send(f"Image text in {ctx.the_channel.mention} `{'enabled' if value == 1 else 'disabled'}`")

    @config.command()
    async def imagelinks(self, ctx, value):
        """Post images as links instead of embeds?"""
        value = text_to_int_bool(value)
        if value is None:
            return await ctx.send(f"Invalid value `{value}`. Use `true` or `false`")

        db.change_setting(ctx.the_channel.id, 'image_links', value)
        await ctx.send(f"Images as links in {ctx.the_channel.mention} `{'enabled' if value == 1 else 'disabled'}`")

    @commands.command()
    async def list(self, ctx, channel=None):
        """List all followed accounts on server or channel"""
        channel_limit = None
        show_inactive = False
        if channel is not None:
            if channel == "inactive":
                show_inactive = True
            else:
                channel_limit = await utils.get_channel(ctx, channel)
                if channel_limit is None:
                    return await ctx.send(f"Invalid channel `{channel}`")

        followers = db.get_user_ids()

        rows = []
        for user_id in followers:
            channel_mentions = []
            for channel_id in db.get_channels(user_id):
                channel = ctx.guild.get_channel(channel_id)
                if channel is not None:
                    if channel_limit is not None and not channel == channel_limit:
                        continue
                    channel_mentions.append(channel.mention)

            if channel_mentions:
                if channel_limit is not None:
                    userdata = db.get_user_data(user_id, limit=channel_limit.id)
                    if not show_inactive or (show_inactive and userdata[1] == 0):
                        rows.append(f"`{userdata[0]}` : **{userdata[1]}** tweets **{userdata[2]}** images")
                else:
                    userdata = db.get_user_data(user_id)
                    if not show_inactive or (show_inactive and userdata[1] == 0):
                        rows.append(f"`{userdata[0]}` : **{userdata[1]}** tweets **{userdata[2]}** images **>>** "
                                    f"{'/'.join(channel_mentions)}")

        if not rows:
            return await ctx.send(f"I am not following any users on this "
                                  f"{'server' if channel_limit is None else 'channel'} yet!")

        content = discord.Embed()
        if channel_limit is not None:
            content.title = f"Followed users in **#{channel_limit.name}**"
        else:
            content.title = f"Followed users in **{ctx.guild.name}**"

        await utils.send_as_pages(ctx, content, rows)

    @commands.command(hidden=True)
    @commands.is_owner()
    async def guilds(self, ctx):
        """Show all connected guilds"""
        membercount = len(set(self.client.get_all_members()))
        content = discord.Embed(title=f"Total **{len(self.client.guilds)}** guilds, **{membercount}** unique users")

        rows = []
        for guild in sorted(self.client.guilds, key=lambda x: x.member_count, reverse=True):
            rows.append(f"[`{guild.id}`] **{guild.member_count}** members : **{guild.name}**")

        await utils.send_as_pages(ctx, content, rows)

    @commands.command(hidden=True)
    @commands.is_owner()
    async def leaveguild(self, ctx, guild_id):
        """Leave a guild"""
        guild = self.client.get_guild(int(guild_id))
        await guild.leave()
        await ctx.send(f"Left the guild `{guild.name}`:`{guild.id}`")
        print(f"Left the guild `{guild.name}`:`{guild.id}`")


def setup(client):
    client.add_cog(Commands(client))


def text_to_int_bool(value):
    if value.lower() in ["true", "yes", "enable", "1"]:
        return 1
    elif value.lower() in ["false", "no", "disable", "0"]:
        return 0
    else:
        return None


def get_commits(author, repository):
    url = f"https://api.github.com/repos/{author}/{repository}/commits"
    response = requests.get(url)
    data = json.loads(response.content.decode('utf-8'))
    return data
