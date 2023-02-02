import asyncio
import sys
import discord
from discord.ext import commands, tasks
from tweepy import StreamRule, Tweet
from tweepy.asynchronous import AsyncClient, AsyncStreamingClient

from modules import queries
from modules.siniara import Siniara
from modules.twitter import TwitterRenderer
from loguru import logger


class RunForeverClient(AsyncStreamingClient):
    def __init__(self, bot, **kwargs):
        self.bot: "Siniara" = bot
        self.twitter_renderer = TwitterRenderer(self.bot)
        super().__init__(**kwargs)

    def run_forever(self) -> asyncio.Task:
        async def task():
            while True:
                await self.filter(tweet_fields=["author_id"])
                if sys.exc_info()[0] == KeyboardInterrupt:
                    break

        return asyncio.create_task(task())

    async def on_tweet(self, tweet: Tweet) -> None:
        asyncio.ensure_future(self.send_to_channels(tweet))

    async def send_to_channels(self, tweet: Tweet):
        channel_ids = await queries.get_channels(self.bot.db, tweet.author_id)
        if not channel_ids:
            logger.warning(f"No channel ids found for user id {tweet.author_id} {tweet}")
            return

        channels = []
        for channel_id in channel_ids:
            channel = self.bot.get_channel(channel_id)
            if channel:
                channels.append(channel)
            else:
                logger.warning(f"Could not find channel with id {channel_id} for tweet {tweet}")

        if channels:
            await self.twitter_renderer.send_tweet(tweet.id, channels)


class Streamer(commands.Cog):
    NO_RETWEETS = " -is:retweet"

    def __init__(self, bot):
        self.bot: "Siniara" = bot

    async def cog_load(self):
        self.api = AsyncClient(
            bearer_token=self.bot.config.twitter_bearer_token,
            wait_on_rate_limit=True,
        )
        self.stream = RunForeverClient(
            self.bot,
            bearer_token=self.bot.config.twitter_bearer_token,
        )
        self.stream.run_forever()
        self.refresh_loop.start()
        self.status_loop.start()

    def rule_builder(self, users: list[str]) -> list[StreamRule]:
        if len(users) == 0:
            return []

        rules = []
        rule_value = "from:" + str(users[0])
        for user in users[1:]:
            addition = " OR from:" + str(user)
            if len(rule_value + addition + self.NO_RETWEETS) <= 510:
                rule_value += addition
            else:
                rules.append(f"({rule_value}){self.NO_RETWEETS}")
                rule_value = "from:" + str(user)
        if rule_value:
            rules.append(f"({rule_value}){self.NO_RETWEETS}")

        return [StreamRule(value) for value in rules]

    def deconstruct_rules(self, rules: list[StreamRule]) -> list[str]:
        usernames = []
        for rule in rules:
            value = rule.value.removesuffix(self.NO_RETWEETS).strip("()")
            usernames += [x.split(":")[1] for x in value.split(" OR ")]
        return usernames

    async def cog_unload(self):
        self.stream.disconnect()

    @tasks.loop(minutes=5)
    async def status_loop(self):
        followed_users = await queries.get_all_users(self.bot.db)
        print("following", followed_users)
        await self.bot.change_presence(
            activity=discord.Activity(name=f"{len(followed_users)} accounts", type=3)
        )

    @tasks.loop(minutes=1)
    async def refresh_loop(self):
        try:
            await self.check_for_filter_changes()
        except Exception as e:
            logger.error("Unhandled exception in refresh loop")
            logger.error(e)
            raise e

    @refresh_loop.before_loop
    @status_loop.before_loop
    async def before_refresh_loop(self):
        await self.bot.wait_until_ready()

    async def replace_rules(self, current_rules: list[StreamRule], new_rules: list[StreamRule]):
        if current_rules:
            await self.stream.delete_rules([r.id for r in current_rules])
        if new_rules:
            response = await self.stream.add_rules(new_rules)
            if response.errors:  # type: ignore
                logger.error(response.errors)  # type: ignore
            logger.info(f"Added new ruleset {new_rules}")

    async def check_for_filter_changes(self):
        current_rules = await self.stream.get_rules()
        current_rules = current_rules.data or []  # type: ignore
        followed_users = await queries.get_all_users(self.bot.db)
        current_users = self.deconstruct_rules(current_rules)
        if set(followed_users) != set(current_users):
            new_rules = self.rule_builder(followed_users)
            await self.replace_rules(current_rules, new_rules)


async def setup(bot: Siniara):
    await bot.add_cog(Streamer(bot))
