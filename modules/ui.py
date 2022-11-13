from typing import Generic, TypeVar

import discord

from modules import queries

T = TypeVar("T")
STYLE = discord.ButtonStyle.blurple


class BaseButtonPaginator(Generic[T], discord.ui.View):
    """
    The Base Button Paginator class. Will handle all page switching without
    you having to do anything.

    Attributes
    ----------
    entries: list[Any]
        A list of entries to get spread across pages.
    per_page: :class:`int`
        The number of entries that get passed onto one page.
    pages: list[list[Any]]
        A list of pages which contain all entries for that page.
    clamp_pages: :class:`bool`
        Whether or not to clamp the pages to the min and max.
    """

    def __init__(
        self,
        *,
        entries: list[T],
        per_page: int,
        clamp_pages: bool = True,
    ) -> None:
        super().__init__(timeout=180)
        self.entries: list[T] = entries
        self.per_page: int = per_page
        self.clamp_pages: bool = clamp_pages
        self._current_page = 0
        self.pages = [entries[i : i + per_page] for i in range(0, len(entries), per_page)]
        self.page_number.label = f"Page {self._current_page + 1} of {self.max_page}"

    @property
    def max_page(self) -> int:
        """:class:`int`: The max page count for this paginator."""
        return len(self.pages)

    @property
    def min_page(self) -> int:
        """:class:`int`: The min page count for this paginator."""
        return 1

    @property
    def current_page(self) -> int:
        """:class:`int`: The current page the user is on."""
        return self._current_page + 1

    @property
    def total_pages(self) -> int:
        """:class:`int`: Returns the total amount of pages."""
        return len(self.pages)

    async def format_page(self, entries: list[T], /) -> discord.Embed:
        """|coro|

        Used to make the embed that the user sees.

        Parameters
        ----------
        entries: List[Any]
            A list of entries for the current page.

        Returns
        -------
        :class:`discord.Embed`
            The embed for this page.
        """
        raise NotImplementedError("Subclass did not overwrite format_page coro.")

    def _switch_page(self, count: int, /) -> list[T]:
        self._current_page += count

        if self.clamp_pages:
            if count < 0:  # Going down
                if self._current_page < 0:
                    self._current_page = self.max_page - 1
            elif count > 0:  # Going up
                if self._current_page > self.max_page - 1:  # - 1 for indexing
                    self._current_page = 0

        self.page_number.label = f"Page {self._current_page + 1} of {self.max_page}"
        return self.pages[self._current_page]

    @discord.ui.button(emoji="<:left:997949561911918643>", style=STYLE)
    async def on_arrow_backward(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        entries = self._switch_page(-1)
        embed = await self.format_page(entries)
        return await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="...", style=STYLE, disabled=True)
    async def page_number(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        pass

    @discord.ui.button(emoji="<:right:997949563665133570>", style=STYLE)
    async def on_arrow_forward(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        entries = self._switch_page(1)
        embed = await self.format_page(entries)
        return await interaction.response.edit_message(embed=embed, view=self)

    async def run(self, context):
        embed = await self.format_page(self.pages[0])
        if self.total_pages > 1:
            if isinstance(context, discord.Interaction):
                await respond_or_followup(context, embed=embed, view=self)
            else:
                await context.send(embed=embed, view=self)
        else:
            # no need to paginate at all
            if isinstance(context, discord.Interaction):
                await respond_or_followup(context, embed=embed)
            else:
                await context.send(embed=embed)


class RowPaginator(BaseButtonPaginator):
    def __init__(self, base_embed, entries, per_page=10, **kwargs):
        self.embed = base_embed
        super().__init__(entries=entries, per_page=per_page, **kwargs)

    async def format_page(self, entries):
        self.embed.description = "\n".join(entries)
        return self.embed


class Confirm(discord.ui.View):
    def __init__(self, content=None, embed=None):
        super().__init__()
        self.value = None
        self.content = content
        self.embed = embed
        self.message = None
        self.interaction = None

    async def run(self, context):
        if isinstance(context, discord.Interaction):
            await respond_or_followup(context, content=self.content, embed=self.embed, view=self)
        else:
            self.message = await context.send(self.content, embed=self.embed, view=self)
        return self

    @discord.ui.button(emoji="<:confirm:997952848677589074>", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        await self.finalize(interaction, button.emoji)

    @discord.ui.button(emoji="<:cancel:997952847167623259>", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        await self.finalize(interaction, button.emoji)

    async def finalize(self, interaction, emoji):
        self.stop()
        if self.message:
            await self.message.delete()
        else:
            if self.content:
                new_content = f"{interaction.message.content} {emoji}"
            else:
                new_content = None
            await interaction.response.edit_message(content=new_content, view=None)


class BooleanSelect(discord.ui.Select):
    def __init__(self, default, **kwargs):
        super().__init__(**kwargs)
        self.options = [
            discord.SelectOption(label="Yes", value="True", default=default is True),
            discord.SelectOption(label="No", value="False", default=default is False),
        ]

    async def callback(self, interaction):
        await interaction.response.defer()


class BooleanMenu(discord.ui.View):
    def __init__(self, default, on_confirm):
        super().__init__()
        self.on_confirm = on_confirm
        self.default = default
        self.select = BooleanSelect(default, row=0)
        self.add_item(self.select)

    @discord.ui.button(label="Ok", row=1)
    async def ok_button(self, interaction, button):
        try:
            value = self.select.values[0]
        except IndexError:
            value = self.default
        await self.on_confirm(value == "True", interaction)

    @discord.ui.button(label="Cancel", row=1)
    async def cancel_button(self, interaction, button):
        await interaction.response.defer()
        self.stop()


ON_OFF = ["<:onbutton:998244221381263411>", "<:offbutton:998244219858731088>"]
CHECK_MARK = "\U00002705"
NO_ENTRY = "\U0001f6ab"


class SettingsMenu(discord.ui.View):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.embed = discord.Embed(title="Send only tweets with media?")

    @discord.ui.button(label="Server wide")
    async def server_wide_toggle(self, interaction, button):
        button.value = (button.value + 1) % 2
        button.emoji = ON_OFF[button.value]
        await queries.set_config_guild(
            self.bot.db, interaction.guild_id, "media_only", button.value
        )
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Channel rules")
    async def channel_rules(self, interaction, button):
        await ChannelRules(self).render(interaction)

    @discord.ui.button(label="User rules")
    async def user_rules(self, interaction, button):
        await UserRules(self).render(interaction)

    async def render(self, interaction):
        guild_setting = await self.bot.db.execute(
            "SELECT media_only FROM guild_settings WHERE guild_id = %s",
            interaction.guild_id,
            one_value=True,
        )
        value = 1 if guild_setting else 0
        self.server_wide_toggle.value = value  # type: ignore
        self.server_wide_toggle.emoji = ON_OFF[value]
        await interaction.response.send_message(embed=self.embed, view=self)


class SubMenu(discord.ui.View):
    def __init__(self, parent_view):
        super().__init__()
        self.parent_view = parent_view

    @discord.ui.button(label="Back")
    async def go_back(self, interaction, button):
        await self.parent_view.render(interaction)

    async def update_embed(self, interaction):
        return discord.Embed(title="you forgot to override update_embed")

    async def render(self, interaction):
        self.embed = await self.update_embed(interaction)
        await interaction.response.edit_message(embed=self.embed, view=self)


class RemoveRule(SubMenu):
    def __init__(self, parent_view, table, options):
        super().__init__(parent_view)
        self.selected_rule.options = options
        self.table = table
        self.go_back.row = 1

    @discord.ui.select(row=0)
    async def selected_rule(self, interaction, select):
        await interaction.client.db.execute(
            f"DELETE FROM {self.table} WHERE rule_id = %s",
            int(select.values[0]),
        )
        select.options = list(filter(lambda x: str(x.value) != select.values[0], select.options))
        if not select.options:
            self.remove_item(select)
        await interaction.response.edit_message(view=self)
        await interaction.followup.send("Rule removed", ephemeral=True)

    async def update_embed(self, interaction):
        return discord.Embed(title="Select rules to remove")


class UserRules(SubMenu):
    async def update_embed(self, interaction):
        user_settings = await interaction.client.db.execute(
            """
            SELECT rule_id, twitter_user.username, media_only
            FROM user_rule RIGHT OUTER JOIN twitter_user
            ON twitter_user.user_id = user_rule.twitter_user_id
            WHERE guild_id = %s
            """,
            interaction.guild_id,
        )
        content = discord.Embed(
            title="User rules",
            description="\n".join(
                f"{':white_check_mark:' if val else ':no_entry_sign:'} **@{uname}** - media only"
                for rule_id, uname, val in user_settings
            ),
        )
        self.options = [
            discord.SelectOption(
                emoji=CHECK_MARK if val else NO_ENTRY,
                label=f"@{uname} - media only",
                value=rule_id,
            )
            for rule_id, uname, val in user_settings
        ]
        if not self.options:
            self.remove_rule.disabled = True

        content.description += "\n\n> Use `/rule user` to add rules."  # type: ignore
        return content

    @discord.ui.button(label="Remove rule")
    async def remove_rule(self, interaction, button):
        await RemoveRule(self, "user_rule", self.options).render(interaction)


class ChannelRules(SubMenu):
    async def update_embed(self, interaction):
        channel_settings = await interaction.client.db.execute(
            "SELECT rule_id, channel_id, media_only FROM channel_rule WHERE guild_id = %s",
            interaction.guild_id,
        )
        content = discord.Embed(
            title="Channel rules",
            description="\n".join(
                f"{':white_check_mark:' if val else ':no_entry_sign:'} <#{cid}> - media only"
                for rule_id, cid, val in channel_settings
            ),
        )
        self.options = [
            discord.SelectOption(
                emoji=CHECK_MARK if val else NO_ENTRY,
                label=f"#{interaction.client.get_channel(cid)} - media only",
                value=rule_id,
            )
            for rule_id, cid, val in channel_settings
        ]
        if not self.options:
            self.remove_rule.disabled = True

        content.description += "\n\n> Use `/rule channel` to add rules."  # type: ignore
        return content

    @discord.ui.button(label="Remove rule")
    async def remove_rule(self, interaction, button):
        await RemoveRule(self, "channel_rule", self.options).render(interaction)


class LinkButton(discord.ui.View):
    def __init__(self, label, url):
        super().__init__()
        button = discord.ui.Button(label=label, url=url)
        self.add_item(button)


async def respond_or_followup(interaction: discord.Interaction, **kwargs):
    if interaction.response.is_done():
        await interaction.followup.send(**kwargs)
    else:
        await interaction.response.send_message(**kwargs)


async def respond_or_send(interaction: discord.Interaction, condition=None, **kwargs):
    if condition is None:
        condition = interaction.response.is_done()
    if condition:
        await interaction.channel.send(**kwargs)  # type: ignore
    else:
        await interaction.response.send_message(**kwargs)


async def followup_or_send(interaction: discord.Interaction, send_if, **kwargs):
    if send_if:
        await interaction.channel.send(**kwargs)  # type: ignore
    else:
        await interaction.followup.send(**kwargs)
