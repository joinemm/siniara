# Project: Fansite Bot
# File: stream.py
# Author: Joinemm
# Date created: 06/04/19
# Python Version: 3.6

import discord
from discord.ext import commands
import logger as log
import tweepy
from tweepy import OAuthHandler
from tweepy import Stream
from tweepy.streaming import StreamListener
import asyncio
import os
import database as db
import utils
import time
import re
import psutil
import math

logger = log.get_logger(__name__)


# twitter credentials
consumer_key = os.environ.get("TWITTER_CONSUMER_KEY")
consumer_secret = os.environ.get("TWITTER_CONSUMER_SECRET")
access_token = os.environ.get("TWITTER_ACCESS_TOKEN")
access_secret = os.environ.get("TWITTER_ACCESS_SECRET")

# tweepy streaming api
auth = OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_secret)
api = tweepy.API(auth, wait_on_rate_limit=True)


class Listener(StreamListener):

    def __init__(self, client, streamcog):
        self.discord_client = client
        self.streamcog = streamcog
        super().__init__()

    def on_connect(self):
        logger.info("Streamer connected")

    def on_status(self, status):
        self.discord_client.loop.create_task(self.streamcog.statushandler(status))
        return True

    def on_error(self, status):
        logger.error(status)
        self.discord_client.loop.create_task(self.streamcog.report_error(status))
        return True

    def on_exception(self, exception):
        logger.error(f"Streamer Error: {exception}")
        self.discord_client.loop.create_task(self.streamcog.report_error(exception))
        return True

    def on_timeout(self):
        logger.error("Stream timed out!")
        self.discord_client.loop.create_task(self.streamcog.report_error("Stream timeout"))
        return True


class Streamer(commands.Cog):

    def __init__(self, client):
        self.client = client
        self.start_time = time.time()
        self.twitterStream = None
        self.run_stream()

    def refresh(self):
        try:
            self.twitterStream.disconnect()
            del self.twitterStream
        except AttributeError:
            pass
        asyncio.sleep(5)
        self.run_stream()

    def get_status(self):
        try:
            return self.twitterStream.running
        except AttributeError:
            return "ERROR"

    def run_stream(self):
        self.twitterStream = Stream(auth, Listener(self.client, self), tweet_mode='extended')
        self.twitterStream.filter(follow=db.get_user_ids(), is_async=True)

    async def update_activity(self):
        await self.client.change_presence(activity=discord.Activity(name=f'{len(db.get_user_ids())} Fansites', type=3))

    async def on_ready(self):
        await self.update_activity()

    async def report_error(self, data):
        channel = self.client.get_channel(508668551658471424)
        if channel is None:
            logger.error(str(data))
        await channel.send(str(data))

    async def send_tweet(self, tweet):
        # send to channels
        for channel_id in db.get_channels(tweet.user.id):
            channel = self.client.get_channel(id=channel_id)
            if channel is None:
                logger.error(f"Unable to get channel {channel_id} for user {tweet.user.screen_name}")
                continue

            await self.send_tweet_embed(channel, tweet)

    async def send_tweet_embed(self, channel, tweet, automatic=True):
        post_text = tweet.full_text
        # remove shortened links and add expanded ones
        post_text = re.sub(r'\S*t\.co/\S*', '', post_text).strip()
        for link in tweet.entities.get('urls'):
            post_text += '\n\n' + link['expanded_url']

        # get media
        mediafiles = []
        try:
            for media in tweet.extended_entities.get('media'):
                media_type = media['type']
                if media_type in ['animated_gif', 'video']:
                    i = 1
                    content_type = None
                    variant = None
                    while not content_type == 'video/mp4' and not i > len(media['video_info']['variants']):
                        variant = media['video_info']['variants'][-i]
                        content_type = variant['content_type']
                        i += 1
                    media_url = variant['url']
                else:
                    media_url = media['media_url_https']
                mediafiles.append((media_type, media_url))
        except AttributeError:
            pass

        channel_settings = db.get_channel_settings(channel.id)

        content = discord.Embed(colour=int(tweet.user.profile_link_color, 16))
        content.set_author(icon_url=tweet.user.profile_image_url_https,
                           name=f"@{tweet.user.screen_name}",
                           url=f"https://twitter.com/{tweet.user.screen_name}/status/{tweet.id}")

        if mediafiles:

            if channel_settings.image_links == 1:
                # post fansite formatting, eg. @joinemm | 190406
                nums = re.findall(r'(\d{6})', post_text)
                number = " | ".join(nums)
                images = '\n'.join([x[1] + (":orig" if x[0] == 'photo' else "") for x in mediafiles])
                await channel.send(f"```\n{number} | @{tweet.user.screen_name}```"
                                   f"{images}")

            else:
                if channel_settings.image_text == 1:
                    content.description = post_text

                for i, file in enumerate(mediafiles):
                    if file[0] == 'photo':
                        content.set_image(url=file[1] + ":orig")
                        await channel.send(embed=content)
                    else:
                        content._image = None
                        await channel.send(embed=content)
                        await channel.send(file[1])

                    if i == 0:
                        content.description = None
                        content._author = None

        elif channel_settings.text_posts == 1:
            content.description = post_text
            await channel.send(embed=content)

        else:
            return

        if automatic:
            db.add_tweet(channel.id, tweet.user.id, len(mediafiles))
            logger.info(log.tweet(channel, tweet.user.screen_name, len(mediafiles)))

    async def statushandler(self, status):
        """filter status and get tweet object"""
        if utils.filter_tweet(status) is False:
            return

        tweet = api.get_status(str(status.id), tweet_mode='extended', include_entities=True)
        await self.send_tweet(tweet)

    async def add(self, ctx, channel, usernames):
        this_channel = await utils.get_channel(ctx, channel)
        if this_channel is None:
            return await ctx.send(f"Invalid channel `{channel}`")

        changes = False
        for username in usernames:
            response = add_fansite(this_channel.id, username)

            if response:
                await ctx.send(f"Error `{response.get('code')}` adding `{username}` : `{response.get('message')}`")
            else:
                changes = True
                await ctx.send(f"Now following `{username}` in {this_channel.mention}")

        if changes:
            await ctx.send('Use `$reset` to apply changes.')

    async def remove(self, ctx, channel, usernames):
        this_channel = await utils.get_channel(ctx, channel)
        if this_channel is None:
            return await ctx.send(f"Invalid channel `{channel}`")

        changes = False
        for username in usernames:
            response = remove_fansite(this_channel.id, username)
            if response:
                await ctx.send(f"Error `{response.get('code')}` removing `{username}` : `{response.get('message')}`")
            else:
                await ctx.send(f"Removed `{username}` from {this_channel.mention}")

        if changes:
            await ctx.send('Use `$reset` to apply changes.')

    # ~~ COMMANDS ~~

    @commands.command()
    async def get(self, ctx, tweet_id):
        if "status" in tweet_id:
            tweet_id = re.search(r'status/(\d+)', tweet_id).group(1)

        tweet = api.get_status(tweet_id, tweet_mode='extended', include_entities=True)
        await self.send_tweet_embed(ctx.channel, tweet)

    @commands.command(name='add')
    @commands.has_permissions(administrator=True)
    async def addmanual(self, ctx, channel, *usernames):
        """Add an account to the follow list"""
        await self.add(ctx, channel, usernames)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def addlist(self, ctx, channel, url):
        """Add all users from a twitter list"""
        this_channel = await utils.get_channel(ctx, channel)
        if this_channel is None:
            return await ctx.send(f"Invalid channel `{channel}`")

        usernames = list_users(url)

        await self.add(ctx, channel, usernames)

    @commands.command(name='remove')
    @commands.has_permissions(administrator=True)
    async def removemanual(self, ctx, channel, *usernames):
        """Remove an account from the follow list"""
        await self.remove(ctx, channel, usernames)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def removelist(self, ctx, channel, url):
        """Remove all users from a twitter list"""
        this_channel = await utils.get_channel(ctx, channel)
        if this_channel is None:
            return await ctx.send(f"Invalid channel `{channel}`")

        usernames = list_users(url)

        await self.remove(ctx, channel, usernames)

    @commands.command(hidden=True)
    @commands.is_owner()
    async def disconnect(self, ctx):
        """Disconnect the twitter stream"""
        self.twitterStream.disconnect()
        del self.twitterStream
        await ctx.send("Twitter stream disconnected")

    @commands.command()
    @commands.cooldown(1, 120)
    @commands.has_permissions(administrator=True)
    async def reset(self, ctx):
        """Reset the stream; refresh follows and settings"""
        self.refresh()
        await self.update_activity()
        await ctx.send("TwitterStream reinitialized, follow list updated")

    @commands.command(alises=['uptime'])
    async def status(self, ctx):
        """Get the bot's status"""
        up_time = time.time() - self.start_time
        uptime_string = utils.stringfromtime(up_time)

        stime = time.time() - psutil.boot_time()
        system_uptime_string = utils.stringfromtime(stime)

        mem = psutil.virtual_memory()
        pid = os.getpid()
        memory_use = psutil.Process(pid).memory_info()[0]

        content = discord.Embed(title=f"Fansite Bot | version 3.0")
        content.set_thumbnail(url=self.client.user.avatar_url)

        content.add_field(name="Bot process uptime", value=uptime_string)
        content.add_field(name="System CPU Usage", value=f"{psutil.cpu_percent()}%")
        content.add_field(name="System uptime", value=system_uptime_string)
        content.add_field(name="System memory Usage", value=f"{mem.percent}%")
        content.add_field(name="Bot memory usage", value=f"{memory_use / math.pow(1024, 2):.2f}MB")
        content.add_field(name="Stream running", value=str(self.get_status()))

        await ctx.send(embed=content)


def setup(client):
    client.add_cog(Streamer(client))


def add_fansite(channel_id, username):
    """Add new user entry to database
    :returns error dict {code:, message:} or None
    """
    try:
        user = api.get_user(screen_name=username)
        user_id = user.id
    except tweepy.error.TweepError as e:
        return e.args[0][0]

    if db.follow_exists(channel_id, user_id):
        return {'code': 160, 'message': 'User already being followed on this channel.'}
    else:
        db.add_follow(channel_id, user_id, username)
        return None


def remove_fansite(channel_id, username):
    """Remove user entry from the database
    :returns error dict {code:, message:} or None
    """
    try:
        user = api.get_user(screen_name=username)
        user_id = user.id
    except tweepy.error.TweepError as e:
        data = db.query("SELECT user_id FROM follows WHERE username = ?", (username,))
        if data is None:
            return e.args[0][0]
        else:
            user_id = data[0][0]

    if db.follow_exists(channel_id, user_id):
        db.remove_follow(channel_id, user_id)
        return None
    else:
        return {'code': 55, 'message': 'User not found on this channel.'}


def list_users(url):
    url = url.replace('https://', '').split('/')
    user = url[1]
    listname = url[3]
    usernames = [u.screen_name for u in tweepy.Cursor(api.list_members, user, listname).items()]
    return usernames
