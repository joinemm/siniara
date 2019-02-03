# Project: Joinemm-Bot
# File: main.py
# Author: Joinemm
# Date created: 02/02/19
# Python Version: 3.6

from discord.ext import commands
import logger
import os
import database as db

# discord variables
TOKEN = os.environ.get('FANSITE_BOT_TOKEN')
client = commands.Bot(command_prefix="$")
extensions = ['commands', 'events', 'stream']

logs = logger.create_logger(__name__)
database = db.Database()


@client.event
async def on_ready():
    await client.wait_until_ready()
    logs.info("Bot is ready.")

if __name__ == "__main__":
    for extension in extensions:
        try:
            client.load_extension(extension)
            logs.info(f"{extension} loaded successfully")
        except Exception as error:
            logs.error(f"loading extension {extension} failed [{error}]")

    client.run(TOKEN)
