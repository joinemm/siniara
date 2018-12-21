# Project: Joinemm-Bot
# File: events.py
# Author: Joinemm
# Date created: 17/12/18
# Python Version: 3.6

import traceback
from discord.ext import commands


class Events:

    def __init__(self, client):
        self.client = client

    async def on_command_error(self, ctx, error):
        """The event triggered when an error is raised while invoking a command"""

        # This prevents any commands with local handlers being handled here in on_command_error.
        if hasattr(ctx.command, 'on_error'):
            return

        # Allows us to check for original exceptions raised and sent to CommandInvokeError.
        # If nothing is found. We keep the exception passed to on_command_error.
        error = getattr(error, 'original', error)

        # Anything in ignored will return and prevent anything happening.
        if isinstance(error, commands.CommandNotFound):
            print(str(error))
            return
        elif isinstance(error, commands.DisabledCommand):
            print(str(error))
            await ctx.send(f'ERROR: {ctx.command} has been disabled.')
            return
        elif isinstance(error, commands.NoPrivateMessage):
            print(str(error))
            try:
                return await ctx.author.send(f'ERROR: {ctx.command} can not be used in Private Messages.')
            except:
                pass
            return
        elif isinstance(error, commands.NotOwner):
            print(str(error))
            await ctx.send("Sorry, only the owner (Joinemm#1998) can use this command!")
            return
        elif isinstance(error, commands.MissingPermissions):
            print(str(error))
            await ctx.send(f"ERROR: You are missing the required permissions to use this command!")
            return
        elif isinstance(error, commands.BotMissingPermissions):
            print(str(error))
            await ctx.send(f"ERROR: I am missing the required permissions to execute this command!")
            return
        else:
            print(f'Ignoring exception in command {ctx.command}:')
            traceback.print_exception(type(error), error, error.__traceback__)
            await ctx.send(f"```{error}```")


def setup(client):
    client.add_cog(Events(client))
