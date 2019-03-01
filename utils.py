# Project: Joinemm-Bot
# File: utils.py
# Author: Joinemm
# Date created: 03/02/19
# Python Version: 3.6

import tweepy
import main
import stream
import asyncio

database = main.database


def get_follow_ids():
    """Get the ids to follow in a list"""
    return list(database.get_attr("follows", ".").keys())


def add_fansite(username, channel_id):
    """Adds a channel to user's channel list, creating a new user if necessary"""
    try:
        user = stream.api.get_user(screen_name=username)
    except tweepy.error.TweepError as e:
        return e.args[0][0]['code']

    database.set_attr("follows", f"{user.id}.username", user.screen_name)
    return database.append_attr("follows", f"{user.id}.channels", channel_id)


def remove_fansite(username, channel_id):
    """Removes a channel from user's channel list. if no more channels, delete the user"""
    try:
        user = stream.api.get_user(screen_name=username)
        user_id = user.id
    except tweepy.error.TweepError as e:
        user_id = find_user(username)
        if user_id is None:
            return e.args[0][0]['code']

    response = database.delete_attr("follows", f"{user_id}.channels", channel_id)
    if response is False:
        return "User not found in given channel's follow list"
    if len(database.get_attr("follows", f"{user_id}.channels")) == 0:
        database.delete_key("follows", f"{user_id}")
    return True


def find_user(username):
    """find user by id or misc name"""
    for user in database.get_attr("follows", "."):
        if database.get_attr("follows", f"{user}.username") == username:
            return user
        elif user == username:
            return user
        else:
            return None


def filter_tweet(tweet):
    """filter out trash. eg. retweets"""
    if str(tweet.user.id) not in database.get_attr("follows", "."):
        return False
    try:
        # noinspection PyStatementEffect
        tweet.retweeted_status
        return False
    except AttributeError:
        return True


def channel_from_mention(guild, text, default=None):
    text = text.strip("<>#!@")
    try:
        channel = guild.get_channel(int(text))
        if channel is None:
            return default
        return channel
    except ValueError:
        return default


async def page_switcher(client, my_msg, content, pages):
    current_page = 0

    def check(_reaction, _user):
        return _reaction.message.id == my_msg.id and _reaction.emoji in ["⬅", "➡"] \
               and not _user == client.user

    await my_msg.add_reaction("⬅")
    await my_msg.add_reaction("➡")

    while True:
        try:
            reaction, user = await client.wait_for('reaction_add', timeout=3600.0, check=check)
        except asyncio.TimeoutError:
            return
        else:
            try:
                if reaction.emoji == "⬅" and current_page > 0:
                    content.description = pages[current_page - 1]
                    current_page -= 1
                    await my_msg.remove_reaction("⬅", user)
                elif reaction.emoji == "➡":
                    content.description = pages[current_page + 1]
                    current_page += 1
                    await my_msg.remove_reaction("➡", user)
                else:
                    continue
                content.set_footer(text=f"page {current_page + 1} of {len(pages)}")
                await my_msg.edit(embed=content)
            except IndexError:
                continue
