# Project: Joinemm-Bot
# File: main.py
# Author: Joinemm
# Date (re)created: 02/02/19
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
import database as db

# discord variables
TOKEN = os.environ.get('FANSITE_BOT_TOKEN')
client = commands.Bot(command_prefix="$")
extensions = ['commands', 'events']

# logging
logs = logger.create_logger(__name__)

# database
database = db.Database()

# twitter credentials
consumer_key = os.environ.get("TWITTER_CONSUMER_KEY")
consumer_secret = os.environ.get("TWITTER_CONSUMER_SECRET")
access_token = os.environ.get("TWITTER_ACCESS_TOKEN")
access_secret = os.environ.get("TWITTER_ACCESS_SECRET")

# tweepy streaming api
auth = OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_secret)
api = tweepy.API(auth, wait_on_rate_limit=True)


# stream
class Listener(StreamListener):

    def on_status(self, data):
        loop.run_until_complete(post_tweet(data))
        return True

    def on_error(self, status):
        print(status)
        return True


class TwitterStream:

    def __init__(self):
        self.twitterStream = Stream(auth, Listener(), tweet_mode='extended', is_async=True)
        self.twitterStream.filter(follow=get_follow_ids(), is_async=True)

    def refresh(self):
        self.twitterStream.disconnect()
        del self.twitterStream
        self.twitterStream = Stream(auth, Listener(), tweet_mode='extended', is_async=True)
        self.twitterStream.filter(follow=get_follow_ids(), is_async=True)

    def get_status(self):
        return self.twitterStream.running


def get_follow_ids():
    """Get the ids to follow in a list"""
    return list(database.get_attr("follows", ".").keys())


def add_fansite(username, channel_id):
    """Adds a channel to user's channel list, creating a new user if necessary"""
    try:
        user = api.get_user(screen_name=username)
    except tweepy.error.TweepError as e:
        return e.args[0][0]['code']

    database.append_attr("follows", f"{user.id}.channels", channel_id)
    database.set_attr("follows", f"{user.id}.name", user.screen_name)
    return True


def remove_fansite(username, channel_id):
    """Removes a channel from user's channel list. if no more channels, delete the user"""
    try:
        user = api.get_user(screen_name=username)
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
    """find user by id or old name"""
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


async def post_tweet(tweet):
    """posts the tweet into all the channels"""
    if filter_tweet(tweet) is False:
        return

    text = []
    try:
        post_text = tweet.extended_tweet['full_text']
    except AttributeError:
        post_text = tweet.text
    for word in post_text.split(" "):
        if "t.co/" not in word:
            if "#" in word:
                text.append(f"({word})[https://twitter.com/hashtag/{word.strip('#')}]")
            else:
                text.append(word)

    tweet_text = " ".join(text)

    channels = database.get_attr("follows", f"{tweet.user.id}.channels", [])

    media_files = []
    try:
        media = tweet.extended_entities.get('media', [])
    except AttributeError:
        # no media
        content = discord.Embed(colour=int(tweet.user.profile_link_color, 16))
        for channel_id in channels:
            if database.get_attr("config", f"channels.{channel_id}.text_posts", False):
                channel = client.get_channel(int(channel_id))
                content.description = tweet_text
                content.set_author(icon_url=tweet.user.profile_image_url,
                                   name=f"@{tweet.user.screen_name}",
                                   url=f"https://twitter.com/{tweet.user.screen_name}/status/{tweet.id}")
                await channel.send(embed=content)
                logs.info(logger.post_log(channel, tweet.user.screen_name, "text"))
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
        content.set_image(url=file[1])
        content.set_author(icon_url=tweet.user.profile_image_url, name=f"@{tweet.user.screen_name}\n{file[0]}",
                           url=f"https://twitter.com/{tweet.user.screen_name}/status/{tweet.id}")

        for channel_id in channels:
            content.description = None
            if posted_text is False and database.get_attr("config", f"channels.{channel_id}.include_text", True):
                content.description = tweet_text

            channel = client.get_channel(int(channel_id))
            await channel.send(embed=content)

            if file[2] is not None:
                content.set_footer(text=f"Contains video/gif")
                await channel.send(file[2])
                logs.info(logger.post_log(channel, tweet.user.screen_name, "video/gif"))
            else:
                logs.info(logger.post_log(channel, tweet.user.screen_name, "photo"))

        posted_text = True
        # add one to amount of images posted
        database.set_attr("follows", f"{tweet.user.id}.images", 1, increment=True)

# setup
loop = asyncio.new_event_loop()
stream = TwitterStream()


# discord events
@client.event
async def on_ready():
    """The event triggered when bot is done loading extensions and is ready to use"""
    logs.info("Bot is ready.")

# load extensions and run the bot
if __name__ == "__main__":
    for extension in extensions:
        try:
            client.load_extension(extension)
            logs.info(f"{extension} loaded successfully")
        except Exception as error:
            logs.error(f"loading extension {extension} failed [{error}]")

    client.run(TOKEN)
