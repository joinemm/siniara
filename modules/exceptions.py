from discord.ext import commands


class SubcommandNotFound(commands.UserInputError):
    pass


class Info(commands.CommandError):
    pass


class Warning(commands.CommandError):
    pass


class Error(commands.CommandError):
    pass
