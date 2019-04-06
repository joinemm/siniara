# Project: Fansite Bot
# File: utils.py
# Author: Joinemm
# Date created: 06/04/19
# Python Version: 3.6

import database as db
import asyncio
from discord.ext import commands
import discord
import copy


def filter_tweet(status):
    """filter out trash. eg. retweets"""
    if str(status.user.id) not in db.get_user_ids():
        return False
    try:
        # noinspection PyStatementEffect
        status.retweeted_status
        return False
    except AttributeError:
        return True


async def get_channel(ctx, mention):
    try:
        return await commands.TextChannelConverter().convert(ctx, mention)
    except commands.errors.BadArgument:
        return None


class TwoWayIterator:

    def __init__(self, list_of_stuff):
        self.items = list_of_stuff
        self.index = 0

    def next(self):
        if not self.index == len(self.items) - 1:
            self.index += 1
        return self.items[self.index]

    def previous(self):
        if not self.index == 0:
            self.index -= 1
        return self.items[self.index]

    def current(self):
        return self.items[self.index]


def create_pages(content, rows, maxrows=15):
    """
    :param content : Embed object to use as the base
    :param rows    : List of rows to use for the embed description
    :param maxrows : Maximum amount of rows per page
    :returns       : List of Embed objects
    """
    pages = []
    content.description = ""
    thisrow = 0
    for row in rows:
        thisrow += 1
        if len(content.description) + len(row) < 2000 and thisrow < maxrows+1:
            content.description += f"\n{row}"
        else:
            thisrow = 0
            pages.append(content)
            content = copy.deepcopy(content)
            content.description = f"{row}"
    if not content.description == "":
        pages.append(content)
    return pages


async def page_switcher(ctx, pages):
    """
    :param ctx    : Context
    :param pages  : List of embeds to use as pages
    """
    pages = TwoWayIterator(pages)
    pages.current().set_footer(text=f"page 1 of {len(pages.items)}")
    msg = await ctx.send(embed=pages.current())

    async def switch_page(content):
        content.set_footer(text=f"page {pages.index + 1} of {len(pages.items)}")
        await msg.edit(embed=content)

    async def previous_page():
        content = pages.previous()
        await switch_page(content)

    async def next_page():
        content = pages.next()
        await switch_page(content)

    functions = {"⬅": previous_page,
                 "➡": next_page}

    await reaction_buttons(ctx, msg, functions)


async def reaction_buttons(ctx, message, functions, timeout=600.0, only_author=False, single_use=False):
    """Handler for reaction buttons
    :param message     : message to add reactions to
    :param functions   : dictionary of {emoji : function} pairs. functions must be async. return True to exit
    :param timeout     : float, default 10 minutes (600.0)
    :param only_author : only allow the user who used the command use the buttons
    :param single_use  : delete buttons after one is used
    """

    for emoji in functions:
        await message.add_reaction(emoji)

    def check(_reaction, _user):
        return _reaction.message.id == message.id \
               and _reaction.emoji in functions \
               and not _user == ctx.bot.user \
               and (_user == ctx.author or not only_author)

    while True:
        try:
            reaction, user = await ctx.bot.wait_for('reaction_add', timeout=timeout, check=check)
        except asyncio.TimeoutError:
            break
        else:
            exits = await functions[str(reaction.emoji)]()
            await message.remove_reaction(reaction.emoji, user)
            if single_use or exits is True:
                break

    try:
        for emoji in functions:
            await message.remove_reaction(emoji, ctx.bot.user)
    except discord.errors.NotFound:
        pass


def stringfromtime(t):
    """
    :param t : Time in seconds
    :returns : Formatted string
    """
    m, s = divmod(t, 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)

    components = []
    if d > 0:
        components.append(f"{int(d)} day" + ("s" if d > 1 else ""))
    if h > 0:
        components.append(f"{int(h)} hour" + ("s" if h > 1 else ""))
    if m > 0:
        components.append(f"{int(m)} minute" + ("s" if m > 1 else ""))
    if s > 0:
        components.append(f"{int(s)} second" + ("s" if s > 1 else ""))

    return " ".join(components)