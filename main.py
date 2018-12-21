# Project: Joinemm-Bot
# File: main.py
# Author: Joinemm
# Date created: 16/12/18
# Python Version: 3.6

from discord.ext import commands
import os

TOKEN = os.environ.get('FANSITE_BOT_TOKEN')
if TOKEN is None:
    print("WARNING: couldn't get bot token")

client = commands.Bot(command_prefix="$")
extensions = ['twitter_stream', 'events']


@client.event
async def on_ready():
    """The event triggered when bot is done loading extensions and is ready to use"""
    print("Bot is ready.")


if __name__ == "__main__":
    for extension in extensions:
        try:
            client.load_extension(extension)
            print(f"{extension} loaded successfully")
        except Exception as error:
            print(f"ERROR: {extension} loading failed [{error}]")

    client.run(TOKEN)
