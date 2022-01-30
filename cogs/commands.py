import discord
from discord.ext import commands
from modules import logger as log, menus, database_actions as queries
import psutil
import os
import math
import time

logger = log.get_logger(__name__)


class Commands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def info(self, ctx):
        """Get information about the bot."""
        followcount = len(await queries.get_filter(self.bot.db))
        content = discord.Embed(title="Siniara v5.1", colour=self.bot.twitter_blue)
        content.description = (
            f"Bot for fetching new media content from twitter, "
            f"created by **Joinemm#7184** <@{self.bot.owner_id}>\n\n"
            f"use `{self.bot.command_prefix}help` for the list of commands.\n\n"
            f"Currently following **{followcount}** twitter accounts "
            f"across **{len(self.bot.guilds)}** guilds."
        )
        content.add_field(
            name="Github", value="https://github.com/joinemm/siniara", inline=False
        )
        content.add_field(name="Donate", value="https://www.ko-fi.com/joinemm", inline=False)
        content.set_thumbnail(url=self.bot.user.avatar_url)
        await ctx.send(embed=content)

    @commands.command(alises=["uptime"])
    async def system(self, ctx):
        """Get the status of the bot's server."""
        up_time = time.time() - self.bot.start_time
        uptime_string = stringfromtime(up_time, 2)
        stime = time.time() - psutil.boot_time()
        system_uptime_string = stringfromtime(stime, 2)
        mem = psutil.virtual_memory()
        pid = os.getpid()
        memory_use = psutil.Process(pid).memory_info()[0]

        content = discord.Embed(title="System status", color=self.bot.twitter_blue)
        content.add_field(name="Bot uptime", value=uptime_string)
        content.add_field(name="System uptime", value=system_uptime_string)
        content.add_field(name="Bot memory usage", value=f"{memory_use / math.pow(1024, 2):.2f}MB")
        content.add_field(name="System memory Usage", value=f"{mem.percent}%")
        content.add_field(name="System CPU Usage", value=f"{psutil.cpu_percent()}%")
        content.add_field(name="Discord API latency", value=f"{self.bot.latency * 1000:.1f}ms")

        await ctx.send(embed=content)

    @commands.command()
    async def ping(self, ctx):
        """Get the bot's ping."""
        pong_msg = await ctx.send(":ping_pong:")
        sr_lat = (pong_msg.created_at - ctx.message.created_at).total_seconds() * 1000
        content = discord.Embed(color=self.bot.twitter_blue)
        content.add_field(
            name=":heartbeat: Heartbeat", value=f"`{self.bot.latency * 1000:.1f}`ms", inline=False
        )
        content.add_field(name=":handshake: ACK", value=f"`{sr_lat}`ms", inline=False)
        await pong_msg.edit(content=None, embed=content)

    @commands.command()
    @commands.is_owner()
    async def guilds(self, ctx):
        """Show all connected guilds."""
        content = discord.Embed(
            title=f"Active in {len(self.bot.guilds)}** guilds",
            color=self.bot.twitter_blue,
        )

        rows = []
        for i, guild in enumerate(
            sorted(self.bot.guilds, key=lambda x: x.member_count, reverse=True), start=1
        ):
            rows.append(
                f"`#{i:2}`[`{guild.id}`] **{guild.member_count}** members : **{guild.name}**"
            )

        pages = menus.Menu(source=menus.ListMenu(rows, embed=content), clear_reactions_after=True)
        await pages.start(ctx)

    @commands.command(hidden=True)
    @commands.is_owner()
    async def leaveguild(self, ctx, guild_id: int):
        """Leave a guild."""
        guild = self.bot.get_guild(guild_id)
        await guild.leave()
        await ctx.send(f":wave: Left **{guild.name}** [`{guild.id}`]")

    @commands.command(name="db", aliases=["dbe", "dbq"])
    @commands.is_owner()
    async def database_query(self, ctx, *, statement):
        """Execute something against the local MariaDB instance."""
        data = await self.bot.db.execute(statement)
        await ctx.send(f"```py\n{data}\n```")

    @commands.command()
    @commands.is_owner()
    async def unlock(self, ctx, guild: discord.Guild = None):
        """Unlock the followed users limit for given guild."""
        if guild is None:
            guild = ctx.guild

        await queries.unlock_guild(self.bot.db, guild.id)
        await ctx.send(f":unlock: Account limit unlocked in **{guild.name}**")


def setup(bot):
    bot.add_cog(Commands(bot))


def stringfromtime(t, accuracy=4):
    """
    :param t : Time in seconds
    :returns : Formatted string
    """
    m, s = divmod(t, 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)

    components = []
    if d > 0:
        components.append(f"{int(d)} day" + ("s" if d > 1 else ""))
    if h > 0:
        components.append(f"{int(h)} hour" + ("s" if h > 1 else ""))
    if m > 0:
        components.append(f"{int(m)} minute" + ("s" if m > 1 else ""))
    if s > 0:
        components.append(f"{int(s)} second" + ("s" if s > 1 else ""))

    return " ".join(components[:accuracy])
