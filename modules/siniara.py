import traceback
from time import time

import aiohttp
import discord
from discord.ext import commands

from modules import helpcommand
from modules import logger as log
from modules import maria
from modules.config import Config


class Siniara(commands.AutoShardedBot):
    def __init__(self, **kwargs):
        self.config = Config()
        intents = discord.Intents.none()
        intents.guilds = True
        intents.messages = True
        intents.reactions = True
        intents.message_content = True
        super().__init__(
            help_command=helpcommand.EmbedHelpCommand(),
            case_insensitive=True,
            command_prefix=self.config.prefix,
            owner_id=int(self.config.owner_id),
            intents=intents,
            description="Bot for following twitter users on discord",
            allowed_mentions=discord.AllowedMentions(everyone=False),
            **kwargs,
        )
        self.logger = log.get_logger("Siniara")
        self.start_time = time()
        self.twitter_blue = int("1da1f2", 16)
        self.db = maria.MariaDB(self)
        self.cogs_to_load = [
            "cogs.commands",
            "cogs.errorhandler",
            "cogs.asyncstreamer",
            "cogs.twitter",
        ]

    async def close(self):
        await self.session.close()
        await self.db.cleanup()
        await super().close()

    async def on_ready(self):
        self.logger.info(f"Logged in as {self.user}")

    async def setup_hook(self):
        self.session = aiohttp.ClientSession()
        self.before_invoke(self.before_any_command)
        await self.db.initialize_pool()
        for extension in self.cogs_to_load:
            try:
                await self.load_extension(extension)
                self.logger.info(f"Imported {extension}")
            except Exception as error:
                self.logger.error(f"Error loading {extension} , aborting")
                traceback.print_exception(type(error), error, error.__traceback__)
                quit()
        self.logger.info("All extensions loaded successfully")

    @staticmethod
    async def before_any_command(ctx):
        """Runs before any command."""
        ctx.time = time()
        try:
            await ctx.typing()
        except discord.errors.Forbidden:
            pass

    async def on_command_completion(self, ctx):
        # prevent double invocation for subcommands
        if ctx.invoked_subcommand is None:
            took = time() - ctx.time
            self.logger.info(
                f"({took:.2f}s) {ctx.author.name}@[{ctx.guild.name}] used {ctx.message.content}"
            )
