# Project: Fansite Bot
# File: main.py
# Author: Joinemm
# Date created: 06/04/19
# Python Version: 3.6

from discord.ext import commands
import logger as log
import os


logger = log.get_logger(__name__)
command_logger = log.get_command_logger()

TOKEN = os.environ.get('FANSITE_BOT_TOKEN')
client = commands.Bot(command_prefix="$", case_insensitive=True, owner_id=133311691852218378)
extensions = ['commands', 'events', 'stream']


@client.event
async def on_ready():
    logger.info("Bot is ready.")


@client.before_invoke
async def before_any_command(ctx):
    await ctx.trigger_typing()
    if ctx.invoked_subcommand is None:
        command_logger.info(log.log_command(ctx))

if __name__ == "__main__":
    for extension in extensions:
        try:
            client.load_extension(extension)
            logger.info(f"{extension} loaded successfully")
        except Exception as error:
            logger.error(f"{extension} loading failed [{error}]")

    client.run(TOKEN)
