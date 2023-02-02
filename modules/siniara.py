import traceback
from time import time

import aiohttp
import discord
from discord import Interaction
from discord.app_commands import CommandTree
from discord.ext import commands
from tweepy.asynchronous import AsyncClient

from modules import maria
from modules.config import Config

from loguru import logger


class MyTree(CommandTree):
    async def interaction_check(self, interaction: Interaction) -> bool:
        """Runs before any slash command"""
        if interaction.command:
            arguments = [f"{name}: {value}" for name, value in interaction.namespace]
            logger.info(
                f"{interaction.user}: /{interaction.command.qualified_name} {' '.join(arguments)}"
            )
        return True


class Siniara(commands.AutoShardedBot):
    def __init__(self, **kwargs):
        self.config = Config()
        intents = discord.Intents.default()
        intents.guilds = True
        intents.reactions = True
        intents.message_content = True
        super().__init__(
            case_insensitive=True,
            command_prefix=commands.when_mentioned_or(self.config.prefix),
            owner_id=int(self.config.owner_id),
            intents=intents,
            description="Bot for following twitter users on discord",
            allowed_mentions=discord.AllowedMentions(everyone=False),
            tree_cls=MyTree,
            **kwargs,
        )
        self.start_time = time()
        self.twitter_blue = int("1da1f2", 16)
        self.db = maria.MariaDB(self)
        self.cogs_to_load = [
            "cogs.commands",
            "cogs.errorhandler",
            "cogs.asyncstreamer",
            "cogs.twitter",
            "jishaku",
        ]
        # the user will never be none so don't ruin my type checking please
        self.user: discord.ClientUser

    async def close(self):
        await self.session.close()
        await self.db.cleanup()
        await super().close()

    async def on_ready(self):
        logger.info(f"Logged in as {self.user}")

    async def setup_hook(self):
        self.session = aiohttp.ClientSession()
        self.tweepy = AsyncClient(
            bearer_token=self.config.twitter_bearer_token,
            wait_on_rate_limit=True,
        )
        self.before_invoke(self.before_any_command)
        await self.db.initialize_pool()
        for extension in self.cogs_to_load:
            try:
                await self.load_extension(extension)
                logger.info(f"Imported {extension}")
            except Exception as error:
                logger.error(f"Error loading {extension} , aborting")
                traceback.print_exception(type(error), error, error.__traceback__)
                quit()
        logger.info("All extensions loaded successfully")

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
            logger.info(
                f"({took:.2f}s) {ctx.author.name}@[{ctx.guild.name}] used {ctx.message.content}"
            )
