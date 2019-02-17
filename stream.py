# Project: Joinemm-Bot
# File: stream.py
# Author: Joinemm
# Date created: 03/02/19
# Python Version: 3.6

import discord
from discord.ext import commands
import logger
import tweepy
from tweepy import OAuthHandler
from tweepy import Stream
from tweepy.streaming import StreamListener
import asyncio
import os
import main
import utils
import time
import re

database = main.database
log = logger.create_logger(__name__)

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
        log.info("Streamer connected")

    def on_status(self, data):
        self.discord_client.loop.create_task(self.streamcog.post_tweet(data))
        return True

    def on_error(self, status):
        log.error(status)
        self.discord_client.loop.create_task(self.streamcog.report_error(status))
        return True

    def on_exception(self, exception):
        log.error(f"Streamer Error: {exception}")
        self.discord_client.loop.create_task(self.streamcog.report_error(exception))
        return True

    def on_timeout(self):
        log.error("Stream timed out!")
        self.discord_client.loop.create_task(self.streamcog.report_error("Stream timeout"))
        return True


class StreamCog:

    def __init__(self, client):
        self.client = client
        self.start_time = time.time()
        self.run_stream()

    def refresh(self):
        self.twitterStream.disconnect()
        del self.twitterStream
        asyncio.sleep(5)
        self.run_stream()

    def get_status(self):
        try:
            return self.twitterStream.running
        except AttributeError:
            return "ERROR"

    def run_stream(self):
        self.twitterStream = Stream(auth, Listener(self.client, self), tweet_mode='extended')
        self.twitterStream.filter(follow=utils.get_follow_ids(), is_async=True)

    async def update_activity(self):
        await self.client.change_presence(activity=discord.Activity(name=f'{len(utils.get_follow_ids())} Fansites',
                                                                    type=3))

    async def on_ready(self):
        await self.update_activity()

    async def report_error(self, data):
        channel = self.client.get_channel(508668551658471424)
        if channel is None:
            log.error("it brake")
        await channel.send(str(data))

    async def post_tweet(self, tweet):
        """posts the tweet into all the channels"""
        if utils.filter_tweet(tweet) is False:
            return

        text = []
        try:
            post_text = tweet.extended_tweet['full_text']
        except AttributeError:
            post_text = tweet.text
        for word in post_text.split(" "):
            if "t.co/" not in word:
                text.append(word)

        tweet_text = " ".join(text)

        channels = database.get_attr("follows", f"{tweet.user.id}.channels", [])

        media_files = []
        try:
            media = tweet.extended_entities.get('media', [])
        except AttributeError:
            media = None

        # no media
        if media is None:
            content = discord.Embed(colour=int(tweet.user.profile_link_color, 16))
            for channel_id in channels:
                if database.get_attr("config", f"channels.{channel_id}.text_posts", False):
                    # channel = client.get_channel(channel_id)
                    content.description = tweet_text
                    content.set_author(icon_url=tweet.user.profile_image_url,
                                       name=f"@{tweet.user.screen_name}",
                                       url=f"https://twitter.com/{tweet.user.screen_name}/status/{tweet.id}")

                    channel = self.client.get_channel(id=channel_id)
                    if channel is None:
                        log.error("it brake")
                    await channel.send(embed=content)
                    log.info(logger.post_log(channel, tweet.user.screen_name, "text"))
            # add one to amount of text posts
            database.set_attr("follows", f"{tweet.user.id}.text_posts", 1, increment=True)
            return

        # there is media
        hashtags = []
        for hashtag in tweet.entities.get('hashtags', []):
            hashtags.append(f"#{hashtag['text']}")

        for i in range(len(media)):
            media_url = media[i]['media_url_https']
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

        posted_text = False
        for file in media_files:
            content = discord.Embed(colour=int(tweet.user.profile_link_color, 16))
            content.set_image(url=file[1] + ":orig")
            content.set_author(icon_url=tweet.user.profile_image_url, name=f"@{tweet.user.screen_name}\n{file[0]}",
                               url=f"https://twitter.com/{tweet.user.screen_name}/status/{tweet.id}")

            for channel_id in channels:
                content.description = None
                if posted_text is False and database.get_attr("config", f"channels.{channel_id}.include_text", True):
                    if database.get_attr("config", f"channels.{channel_id}.format", False):
                        nums = re.findall(r'(\d{6})', tweet_text)
                        if nums:
                            number = " | ".join(nums)
                            content.description = f"`@{tweet.user.screen_name} | {number}`"
                        else:
                            content.description = tweet_text
                    else:
                        content.description = tweet_text

                channel = self.client.get_channel(id=channel_id)
                if channel is None:
                    log.error("it brake")
                await channel.send(embed=content)
                log.info(logger.post_log(channel, tweet.user.screen_name, "media"))

                if file[2] is not None:
                    content.set_footer(text=f"Contains video/gif")
                    await channel.send(file[2])

            posted_text = True
            # add one to amount of images posted
            database.set_attr("follows", f"{tweet.user.id}.images", 1, increment=True)

    # ~~ COMMANDS ~~

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def add(self, ctx, mention, *usernames):
        """Add an account to the follow list"""
        log.info(logger.command_log(ctx))

        channel = utils.channel_from_mention(ctx.guild, mention)
        if channel is None:
            await ctx.send("Invalid channel")
            return
        for username in usernames:
            response = utils.add_fansite(username, channel.id)
            if response is True:
                await ctx.send(f"Added `{username}` to {channel.mention}. Use $reset to apply changes")
            else:
                await ctx.send(f"Error adding `{username}`: `{response}`")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def remove(self, ctx, mention, *usernames):
        """Remove an account from the follow list"""
        log.info(logger.command_log(ctx))

        channel = utils.channel_from_mention(ctx.guild, mention)
        if channel is None:
            await ctx.send("Invalid channel")
            return
        for username in usernames:
            response = utils.remove_fansite(username, channel.id)
            if response is True:
                await ctx.send(f"Removed `{username}` from {channel.mention}. Use $reset to apply changes")
            else:
                await ctx.send(f"Error removing `{username}`: `{response}`")

    @commands.command()
    @commands.cooldown(1, 120)
    @commands.has_permissions(administrator=True)
    async def reset(self, ctx):
        """Reset the stream; refresh follows and settings"""
        log.info(logger.command_log(ctx))

        self.refresh()
        await self.update_activity()
        await ctx.send("TwitterStream reinitialized, follow list updated")

    @commands.command()
    async def status(self, ctx):
        """Get the bot's status"""
        log.info(logger.command_log(ctx))

        up_time = time.time() - self.start_time
        m, s = divmod(up_time, 60)
        h, m = divmod(m, 60)
        d, h = divmod(h, 24)

        bot_msg = await ctx.send(f"```running = {self.get_status()}\n"
                                 f"heartbeat = {self.client.latency * 1000:.0f}ms\n"
                                 f"roundtrip latency = PENDINGms\n"
                                 f"uptime = {d:.0f} days {h:.0f} hours {m:.0f} minutes {s:.0f} seconds```")

        latency = (bot_msg.created_at - ctx.message.created_at).total_seconds() * 1000
        await bot_msg.edit(content=bot_msg.content.replace("PENDING", str(latency)))


def setup(client):
    client.add_cog(StreamCog(client))
