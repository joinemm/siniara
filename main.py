# Project: Joinemm-Bot
# File: main.py
# Author: Joinemm
# Date created: 16/12/18
# Python Version: 3.6

from discord.ext import commands
import os
import time

TOKEN = os.environ.get('FANSITE_BOT_TOKEN')
if TOKEN is None:
    print("WARNING: couldn't get bot token")

client = commands.Bot(command_prefix="$")
extensions = ['twitter_stream', 'events']

@client.event
async def on_ready():
    """The event triggered when bot is done loading extensions and is ready to use"""
    start_time = time.time()
    print("Bot is ready.")

@commands.command()
async def uptime(ctx):
    up_time = time.time() - start_time
    m, s = divmod(up_time, 60)
    h, m = divmod(m, 60)
    await ctx.send("Current process uptime: %d hours %d minutes %d seconds" % (h, m, s))
    print(f"Uptime requested: {h}:{m}:{s}")

if __name__ == "__main__":
    for extension in extensions:
        try:
            client.load_extension(extension)
            print(f"{extension} loaded successfully")
        except Exception as error:
            print(f"ERROR: {extension} loading failed [{error}]")

    client.run(TOKEN)
