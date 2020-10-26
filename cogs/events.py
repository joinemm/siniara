from time import time
from discord.ext import commands


class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        """Runs when the bot connects to the discord servers"""
        self.bot.logger.info(f"Logged in as {self.bot.user}")

    @commands.Cog.listener()
    async def on_command_completion(self, ctx):
        """Runs when any command is completed succesfully"""
        # prevent double invocation for subcommands
        if ctx.invoked_subcommand is None:
            took = time() - ctx.time
            self.bot.logger.info(
                f"({took:.2f}s) {ctx.author.name}@[{ctx.guild.name}] used {ctx.message.content}"
            )


def setup(bot):
    bot.add_cog(Events(bot))
