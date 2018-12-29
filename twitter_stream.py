# Project: Joinemm-Bot
# File: twitter_stream.py
# Author: Joinemm
# Date created: 16/12/18
# Python Version: 3.6

import json
import tweepy
from tweepy import OAuthHandler
from tweepy import Stream
from tweepy.streaming import StreamListener
import discord
from discord.ext import commands
import asyncio
import os
import time

consumer_key = os.environ.get("TWITTER_CONSUMER_KEY")
consumer_secret = os.environ.get("TWITTER_CONSUMER_SECRET")
access_token = os.environ.get("TWITTER_ACCESS_TOKEN")
access_secret = os.environ.get("TWITTER_ACCESS_SECRET")

auth = OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_secret)
api = tweepy.API(auth)


def load_config():
    with open('config.json', 'r') as filehandle:
        data = json.load(filehandle)
        return data


def save_config(data):
    with open('config.json', 'w') as filehandle:
        json.dump(data, filehandle, indent=4)


def refresh_follows():
    with open('follows.json', 'r') as filehandle:
        data = json.load(filehandle)
        return data


def add_follows(data, channel, usernames):
    for user in usernames:
        if user[0] in data:
            # user already exists in database, possibly adding a new channel
            if int(channel) in data[user[0]]['channels']:
                # already posting this used to this channel
                continue
            else:
                data[user[0]]['channels'].append(int(channel))
        else:
            data[user[0]] = {"id": str(user[1]), "channels": [int(channel)]}
        print(f"adding user [{user}] to followlist channel [{channel}]")

    with open('follows.json', 'w') as filehandle:
        json.dump(data, filehandle, indent=4)


def remove_follows(data, channel, usernames):
    for user in usernames:
        data[user[0]]['channels'].remove(int(channel))
        print(f"removing user [{user}] from followlist channel [{channel}]")
        if len(data[user[0]]['channels']) == 0:
            del(data[user[0]])

    with open('follows.json', 'w') as filehandle:
        json.dump(data, filehandle, indent=4)


class Queue:

    def __init__(self):
        self.queue = list()

    # Adding elements to queue
    def enqueue(self, data):
        print("New tweet queued")
        self.queue.insert(0, data)
        return True

    # Removing the last element from the queue
    def dequeue(self):
        if len(self.queue) > 0:
            return self.queue.pop()
        return None

    def length(self):
        return len(self.queue)


class MyListener(StreamListener):

    def __init__(self):
        self.myQueue = Queue()
        super().__init__()

    def on_status(self, status):
        # print(status)
        try:
            status.retweeted_status
        except AttributeError:
            try:
                self.myQueue.enqueue(status)
            except BaseException as e:
                print("Error on_data: %s" % str(e))
        return True

    def on_error(self, status):
        print("ERROR")
        print(status)
        return True


class TwitterStream:

    def __init__(self, client):
        self.client = client
        self.start_time = time.time()
        self.config_json = load_config()

    async def on_ready(self):
        self.update_follow_ids()
        await self.start_stream()
        while True:
            if not self.twitter_stream.running:
                await self.refresh()
                await self.client.get_channel(508668551658471424).send(f"`Had to reset stream because it wasn't running!`")

            try:
                await self.post_from_queue()
            except Exception as e:
                print("Ignoring exception in refresh loop")
                print(e)
            await asyncio.sleep(self.config_json['refresh_delay'])

    async def start_stream(self):
        print("Starting stream")
        self.twitter_stream = Stream(auth, MyListener(), tweet_mode='extended')
        self.twitter_stream.filter(follow=self.follow_list, is_async=True)
        self.queue = self.twitter_stream.listener.myQueue
        try:
            await self.client.change_presence(activity=discord.Activity(name=f'{len(self.follow_list)} Fansites', type=3))
        except Exception as e:
            print(e)
            await self.client.get_channel(508668551658471424).send(f"```{e}```")

    def update_follow_ids(self):
        self.follow_dict = refresh_follows()
        idlist = []
        for user in self.follow_dict:
            idlist.append(self.follow_dict[user]['id'])
        self.follow_list = idlist

    async def refresh(self):
        self.config_json = load_config()
        self.update_follow_ids()
        self.twitter_stream.disconnect()
        del self.twitter_stream
        await self.start_stream()

    async def post_from_queue(self):
        tweet = self.queue.dequeue()
        #print(tweet)
        if tweet is not None:
            twitter_user = tweet.user.screen_name
            if twitter_user not in self.follow_dict:
                print(f"skipping user [{twitter_user}] not found in follow list")
                return
            channels = self.follow_dict[twitter_user]['channels']

            media_files = []
            try:
                media = tweet.extended_entities.get('media', [])
            except AttributeError:
                # no media
                content = discord.Embed(colour=int(tweet.user.profile_link_color, 16))
                for channel in channels:
                    if str(channel) in self.config_json['channels']:
                        if self.config_json['channels'][str(channel)].get('textmode') == "none":
                            print(f"Skipping text post for {channel}")
                            continue
                    content.description = tweet.text
                    content.set_author(icon_url=tweet.user.profile_image_url,
                                       name=f"@{tweet.user.screen_name}",
                                       url=f"https://twitter.com/{tweet.user.screen_name}/status/{tweet.id}")
                    await self.client.get_channel(channel).send(embed=content)
                return
            hashtags = []
            for hashtag in tweet.entities.get('hashtags', []):
                hashtags.append(f"#{hashtag['text']}")
            for i in range(len(media)):
                media_url = media[i]['media_url']
                video_url = None
                if not media[i]['type'] == "photo":
                    video_urls = media[i]['video_info']['variants']
                    largest_rate = 0
                    for x in range(len(video_urls)):
                        if video_urls[x]['content_type'] == "video/mp4":
                            if video_urls[x]['bitrate'] > largest_rate:
                                largest_rate = video_urls[x]['bitrate']
                                video_url = video_urls[x]['url']
                                media_url = video_urls[x]['url']
                media_files.append((" ".join(hashtags), media_url, video_url))

            print(f"Posting tweet from {twitter_user} - {len(media_files)} images")

            posted_text = False
            for file in media_files:
                content = discord.Embed(colour=int(tweet.user.profile_link_color, 16))
                content.set_image(url=file[1])
                content.set_author(icon_url=tweet.user.profile_image_url, name=f"@{tweet.user.screen_name}\n{file[0]}",
                                   url=f"https://twitter.com/{tweet.user.screen_name}/status/{tweet.id}")

                for channel in channels:
                    content.description = None
                    if str(channel) in self.config_json['channels']:
                        if self.config_json['channels'][str(channel)].get('textmode') == "full" and not posted_text:
                            content.description = tweet.text
                            posted_text = True

                    await self.client.get_channel(channel).send(embed=content)

                    if file[2] is not None:
                        # content.description = f"Contains video/gif [Click here to view]({file[2]})"
                        await self.client.get_channel(channel).send(file[2])

    # --commands

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def add(self, ctx, channel, *usernames):
        """Add an account to the follow list"""
        if ctx.message.guild.get_channel(int(channel)) is not None:
            to_add = []
            for username in usernames:
                try:
                    user = api.get_user(screen_name=username)
                    to_add.append((user.screen_name, user.id))
                except Exception:
                    await ctx.send(f"Error adding user `{username}`")
                    print(f"Error adding user {username}")
            if to_add:
                add_follows(self.follow_dict, channel, to_add)
                await ctx.send(f"{len(to_add)} new users added to follow list of <#{channel}>. Will apply on next reset.")
        else:
            await ctx.send(f"Channel `{channel}` not found on this server!")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def remove(self, ctx, channel, *usernames):
        """Remove an account from the follow list"""
        if ctx.message.guild.get_channel(int(channel)) is not None:
            to_remove = []
            for username in usernames:
                try:
                    user = api.get_user(screen_name=username)
                    if int(channel) in self.follow_dict[user.screen_name]['channels']:
                        to_remove.append((user.screen_name, user.id))
                except Exception:
                    await ctx.send(f"Error adding user `{username}`")
                    print(f"Error adding user {username}")
            if to_remove:
                remove_follows(self.follow_dict, channel, to_remove)
                await ctx.send(f"{len(to_remove)} users removed from follow list of <#{channel}>. Will apply on next reset.")
        else:
            await ctx.send(f"Channel `{channel}` not found on this server!")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def reset(self, ctx):
        """Reset the stream; refresh follows and settings"""
        await self.refresh()
        await ctx.send("Stream reset, follow list updated.")
        print("Stream reset")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def config(self, ctx, param1=None, param2=None, param3=None):
        """Configure bot options."""
        if param1 == "help" or param1 is None:
            await ctx.send("`>config [channel] [setting] [value]`\n"
                           "**settings:** `[textmode | refresh]`\n"
                           "- **textmode:** `[none | partial | full]`\n"
                           "-- `none`: images are posted without text and text-only posts are skipped\n"
                           "-- `partial`: images are posted without text but text-only posts are posted normally\n"
                           "-- `full`: (default) everything is posted with all the text\n"
                           "- **refresh:** time in seconds to wait before checking the queue again for another tweet.\n\n"
                           "example: `>config 124567891069420 textmode full`")
            return
        elif param1 == "refresh":
            if ctx.message.author.id == 133311691852218378:
                self.config_json['refresh_delay'] = int(param2)
                save_config(self.config_json)
                print(f"Set refresh delay to {param2}")
                await ctx.send(f"Set refresh delay to `{param2}`")
                return
            else:
                await ctx.send("ERROR: You are not allowed to change this setting.")

        channel = ctx.message.guild.get_channel(int(param1))
        if channel is None:
            await ctx.send(f"ERROR: Channel `{param1}` not found on this server!")
            return
        if param2 == "textmode":
            if param3 in ["full", "partial", "none"]:
                if param1 not in self.config_json['channels']:
                    self.config_json['channels'][param1] = {}
                self.config_json['channels'][param1]['textmode'] = param3
                save_config(self.config_json)
                print(f"Set textmode for {channel.name} as {param3}")
                await ctx.send(f"Set textmode for {channel.mention} to `{param3}`")
                return
            else:
                await ctx.send(f"ERROR: Invalid parameter `{param3}` for setting `{param2}`. use `>config help` for help.")
                return
        else:
            await ctx.send(f"ERROR: Invalid setting `{param2}`. use `>config help` for help.")

    @commands.command()
    async def list(self, ctx, page=1):
        """List the currently followed accounts on this server."""
        print("Listing followed users")
        nothing = True
        pages = []
        added = 20
        this_page = None
        for name in self.follow_dict:
            if added > 19:
                added = 0
                if this_page is not None:
                    pages.append(this_page)
                this_page = discord.Embed()
                this_page.title = "Currently followed accounts on this server:"
                this_page.description = ""

            channels_s = ""
            no_channels = True
            for channel in self.follow_dict[name]['channels']:
                if ctx.message.guild.get_channel(channel) is not None:
                    channels_s += f"<#{channel}>"
                    no_channels = False
            if not no_channels:
                this_page.description += f"\n{name} ({self.follow_dict[name]['id']}) in {channels_s}"
                added += 1
                nothing = False
        pages.append(this_page)
        if nothing:
            await ctx.send("No follows set for this server!")
        else:
            pages[page-1].set_footer(text=f"page {page} of {len(pages)}")
            await ctx.send(embed=pages[page-1])

    @commands.command()
    async def status(self, ctx):
        """Get the bot's status"""
        up_time = time.time() - self.start_time
        m, s = divmod(up_time, 60)
        h, m = divmod(m, 60)
        d, h = divmod(h, 24)

        bot_msg = await ctx.send(f"```running = {self.twitter_stream.running}\n"
                                 f"queue length = {self.queue.length()}\n"
                                 f"refresh delay = {self.config_json['refresh_delay']}s\n"
                                 f"heartbeat = {self.client.latency*1000:.0f}ms\n"
                                 f"roundtrip latency = PENDINGms/n"
                                 f"uptime = {d:.0f} days {h:.0f} hours {m:.0f} minutes {s:.0f} seconds```")

        latency = (bot_msg.created_at-ctx.message.created_at).total_seconds() * 1000
        await bot_msg.edit(content=bot_msg.content.replace("PENDING", str(latency)))

    @commands.command()
    async def patreon(self, ctx):
        """Get a link to the patreon page."""
        await ctx.send("Consider joining my patreon to help with server upkeep costs <:vivismirk2:523308548717805638>"
                       "\nhttps://www.patreon.com/joinemm")

    @commands.command()
    async def info(self, ctx):
        """Get information about the bot."""
        appinfo = await self.client.application_info()
        info_embed = discord.Embed(title='Fansite Tracker Bot',
                                   description=f'This is a bot for tracking fansites on twitter.\n'
                                               f'use the help command for a list of commands.\n\n'
                                               f'Currently tracking {len(self.follow_list)} accounts '
                                               f'across {len(self.client.guilds)} servers.\n\n'
                                               f'Author: {appinfo.owner.mention}',
                                   colour=discord.Colour.magenta())
        info_embed.add_field(name='Patreon', value="https://www.patreon.com/joinemm", inline=False)
        info_embed.set_footer(text='version 1.3')
        info_embed.set_thumbnail(url=self.client.user.avatar_url)
        await ctx.send(embed=info_embed)


def setup(client):
    client.add_cog(TwitterStream(client))
