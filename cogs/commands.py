import math
import time
import typing

import discord
import psutil
from discord import app_commands
from discord.ext import commands

from modules import queries
from modules.siniara import Siniara
from modules.ui import RowPaginator


class Commands(commands.Cog):
    def __init__(self, bot):
        self.bot: Siniara = bot

    @app_commands.command()
    async def info(self, interaction: discord.Interaction):
        """Get information about the bot."""
        userlist = await queries.get_all_users(self.bot.db)
        followcount = len(set(userlist))
        content = discord.Embed(title="Siniara v6", colour=self.bot.twitter_blue)
        content.description = (
            f"Bot for fetching new media content from twitter, "
            f"created by **Joinemm#7184** <@{self.bot.owner_id}>\n\n"
            f"Currently following **{followcount}** twitter accounts "
            f"across **{len(self.bot.guilds)}** guilds."
        )
        content.add_field(name="Github", value="https://github.com/joinemm/siniara", inline=False)
        content.add_field(name="Donate", value="https://www.ko-fi.com/joinemm", inline=False)

        uptime = time.time() - self.bot.start_time
        memory_use = psutil.Process().memory_info()[0]

        content.add_field(name="Bot uptime", value=stringfromtime(uptime, 2))
        content.add_field(name="Bot memory usage", value=f"{memory_use / math.pow(1024, 2):.2f}MB")
        content.add_field(name="Discord API latency", value=f"{self.bot.latency * 1000:.1f}ms")
        content.set_thumbnail(url=self.bot.user.display_avatar.url)

        await interaction.response.send_message(embed=content)

    @app_commands.command()
    async def ping(self, interaction: discord.Interaction):
        """Get the bot's ping."""
        await interaction.response.send_message(f":ping_pong: `{int(self.bot.latency * 1000)}` ms")

    @commands.command(hidden=True)
    @commands.is_owner()
    async def guilds(self, ctx: commands.Context):
        """Show all connected guilds."""
        content = discord.Embed(
            title=f"Active in {len(self.bot.guilds)} guilds",
            color=self.bot.twitter_blue,
        )

        rows = []
        for i, guild in enumerate(
            sorted(self.bot.guilds, key=lambda x: x.member_count, reverse=True), start=1
        ):
            rows.append(
                f"`#{i:2}`[`{guild.id}`] **{guild.member_count}** members : **{guild.name}**"
            )

        await RowPaginator(content, rows).run(ctx)

    @commands.command(hidden=True)
    @commands.is_owner()
    async def leaveguild(self, ctx: commands.Context, guild_id: int):
        """Leave a guild."""
        guild = self.bot.get_guild(guild_id)
        await guild.leave()
        await ctx.send(f":wave: Left **{guild.name}** [`{guild.id}`]")

    @commands.command(name="db", aliases=["dbe", "dbq"])
    @commands.is_owner()
    async def database_query(self, ctx: commands.Context, *, statement: str):
        """Execute something against the local MariaDB instance."""
        data = await self.bot.db.execute(statement)
        await ctx.send(f"```py\n{data}\n```")

    @commands.command()
    @commands.is_owner()
    async def unlock(self, ctx: commands.Context, guild: discord.Guild = None):
        """Unlock the followed users limit for given guild."""
        if guild is None:
            guild = ctx.guild

        await queries.unlock_guild(self.bot.db, guild.id)
        await ctx.send(f":unlock: Account limit unlocked in **{guild.name}**")

    @commands.command()
    @commands.guild_only()
    async def sync(
        self,
        ctx: commands.Context,
        guilds: commands.Greedy[discord.Object],
        spec: typing.Optional[typing.Literal["~", "*", "^"]] = None,
    ) -> None:
        """
        Syncs app commands

        $sync -> global sync
        $sync ~ -> sync current guild
        $sync * -> copies all global app commands to current guild and syncs
        $sync ^ -> clears all commands from the current guild target and syncs (removes guild commands)
        $sync id_1 id_2 -> syncs guilds with id 1 and 2
        """
        if not guilds:
            if spec == "~":
                synced = await ctx.bot.tree.sync(guild=ctx.guild)
            elif spec == "*":
                ctx.bot.tree.copy_global_to(guild=ctx.guild)
                synced = await ctx.bot.tree.sync(guild=ctx.guild)
            elif spec == "^":
                ctx.bot.tree.clear_commands(guild=ctx.guild)
                await ctx.bot.tree.sync(guild=ctx.guild)
                synced = []
            else:
                synced = await ctx.bot.tree.sync()

            await ctx.send(
                f"Synced {len(synced)} commands {'globally' if spec is None else 'to the current guild.'}"
            )
            return

        ret = 0
        for guild in guilds:
            try:
                await ctx.bot.tree.sync(guild=guild)
            except discord.HTTPException:
                pass
            else:
                ret += 1

        await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")


async def setup(bot: Siniara):
    await bot.add_cog(Commands(bot))


def stringfromtime(t: int, accuracy: int = 4) -> str:
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
