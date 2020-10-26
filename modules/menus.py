import discord
from discord.ext import menus


class Menu(menus.MenuPages):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class ListMenu(menus.ListPageSource):
    def __init__(self, data, per_page=10, embed=None):
        if embed is None:
            self.embed = discord.Embed()
        else:
            self.embed = embed

        super().__init__(data, per_page=per_page)

        if self.is_paginating():
            if self.embed.footer.text != discord.Embed.Empty:
                self.og_footer = " | " + self.embed.footer.text
            else:
                self.og_footer = ""

    async def format_page(self, menu, entries):
        self.embed.description = "\n".join(entries)
        if self.is_paginating():
            footer_text = f"{menu.current_page+1}/{self.get_max_pages()}{self.og_footer}"
            self.embed.set_footer(text=footer_text)
        return self.embed
