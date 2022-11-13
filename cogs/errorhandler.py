import traceback

import discord
from discord import app_commands
from discord.ext import commands

from modules.siniara import Siniara

from loguru import logger


class ErrorHandler(commands.Cog):
    def __init__(self, bot):
        self.bot: Siniara = bot
        self.message_levels = {
            "info": {
                "description_prefix": ":information_source:",
                "color": int("3b88c3", 16),
                "help_footer": False,
            },
            "warning": {
                "description_prefix": ":warning:",
                "color": int("ffcc4d", 16),
                "help_footer": True,
            },
            "error": {
                "description_prefix": ":no_entry:",
                "color": int("be1931", 16),
                "help_footer": False,
            },
        }

        # setting the handler
        self.bot.tree.on_error = self.on_app_command_error

    # the error handler
    async def on_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        exc = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        logger.error(exc)
        if interaction.response.is_done():
            await interaction.followup.send(str(error))
        else:
            await interaction.response.send_message(str(error))

    async def send(self, ctx, level, message, help_footer=None):
        """Send error message to chat."""
        settings = self.message_levels.get(level)
        embed = discord.Embed(
            color=settings["color"], description=f"{settings['description_prefix']} `{message}`"
        )

        help_footer = help_footer or settings["help_footer"]
        if help_footer:
            embed.set_footer(text=f"Learn more: {ctx.prefix}help {ctx.command.qualified_name}")

        try:
            await ctx.send(embed=embed)
        except discord.errors.Forbidden:
            logger.error("Forbidden when trying to send error message embed")

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Triggers when an error is raised while invoking a command."""
        error = getattr(error, "original", error)

        # silently ignored expections
        ignored = (commands.CommandNotFound, commands.DisabledCommand)

        # exceptions to send to chat but dont log
        sendtochat = (commands.UserInputError,)

        if isinstance(error, ignored):
            return

        elif isinstance(error, commands.NotOwner):
            await self.send(ctx, "info", "Only my creator can use this command!")

        elif isinstance(error, commands.NoPrivateMessage):
            try:
                await self.send(
                    ctx.author,
                    "info",
                    "This command cannot be used in private messages",
                )
            except discord.HTTPException:
                pass

        elif isinstance(error, commands.MissingRequiredArgument):
            await self.send(
                ctx,
                "warning",
                str(error),
                help_footer=True,
            )

        elif isinstance(error, discord.errors.Forbidden):
            try:
                await self.send(ctx, "error", str(error))
            except discord.errors.Forbidden:
                try:
                    await ctx.message.add_reaction("🙊")
                except discord.errors.Forbidden:
                    await self.log_and_traceback(ctx, error)

        elif isinstance(error, sendtochat):
            await self.send(ctx, "warning", str(error))

        else:
            await self.log_and_traceback(ctx, error)

    async def log_and_traceback(self, ctx, error):
        logger.error(f'Unhandled exception in command "{ctx.message.content}":')
        exc = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        logger.error(exc)
        await self.send(ctx, "error", f"{type(error).__name__}: {error}")


async def setup(bot):
    await bot.add_cog(ErrorHandler(bot))
