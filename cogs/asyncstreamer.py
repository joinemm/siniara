import asyncio
import sys

import discord
from discord.ext import commands, tasks
from tweepy import StreamRule, Tweet
from tweepy.asynchronous import AsyncClient, AsyncStreamingClient

from modules import logger as log
from modules import queries
from modules.siniara import Siniara
from modules.twitter_renderer import TwitterRenderer

logger = log.get_logger(__name__)


class RunForeverClient(AsyncStreamingClient):
    def __init__(self, bot, **kwargs):
        self.bot: Siniara = bot
        self.twitter_renderer = TwitterRenderer(self.bot)
        super().__init__(**kwargs)

    def run_forever(self) -> asyncio.Task:
        async def task():
            while True:
                await self.filter()
                if sys.exc_info()[0] == KeyboardInterrupt:
                    break

        return asyncio.create_task(task())

    async def on_tweet(self, tweet: Tweet) -> None:
        asyncio.ensure_future(self.send_to_channels(tweet))

    async def send_to_channels(self, tweet: Tweet):
        logger.info(tweet)
        channels = await queries.get_channels(self.bot.db, tweet.author_id)
        logger.info(f"sending to {channels}")
        await self.twitter_renderer.send_tweet(
            tweet.id,
            [self.bot.get_channel(c) for c in channels],
        )


class Streamer(commands.Cog):
    def __init__(self, bot):
        self.bot: Siniara = bot

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

        follows = await queries.get_all_users(self.bot.db)
        await self.bot.change_presence(
            activity=discord.Activity(name=f"{len(set(follows))} accounts", type=3)
        )

    def rule_builder(self, users: list[str]) -> list[StreamRule]:
        suffix = " -is:retweet"
        rules = []
        rule_value = "from:" + str(users[0])
        for user in users[1:]:
            addition = " OR from:" + str(user)
            if len(rule_value + addition + suffix) <= 512:
                rule_value += addition
            else:
                rules.append(rule_value + suffix)
                rule_value = "from:" + str(user)

        return [StreamRule(value) for value in rules]

    def deconstruct_rules(self, rules: list[StreamRule]) -> list[str]:
        suffix = " -is:retweet"
        usernames = []
        for rule in rules:
            value = rule.value.removesuffix(suffix)
            usernames += [x.split(":")[1] for x in value.split(" OR ")]
        return usernames

    async def cog_unload(self):
        self.stream.disconnect()

    @tasks.loop(minutes=1)
    async def refresh_loop(self):
        try:
            await self.check_for_filter_changes()
        except Exception as e:
            logger.error("Unhandled exception in refresh loop")
            logger.error(e)
            raise e

    @refresh_loop.before_loop
    async def before_refresh_loop(self):
        await self.bot.wait_until_ready()
        logger.info("Starting streamer refresh loop")

    async def replace_rules(self, current_rules: list[StreamRule], new_rules: list[StreamRule]):
        if current_rules:
            await self.stream.delete_rules([r.id for r in current_rules])
        if new_rules:
            await self.stream.add_rules(new_rules)
            logger.info(f"Added new ruleset {new_rules}")

    async def check_for_filter_changes(self):
        current_rules = await self.stream.get_rules()
        current_rules = current_rules.data or []
        followed_users = set(await queries.get_all_users(self.bot.db))
        current_users = self.deconstruct_rules(current_rules)
        if followed_users != set(current_users):
            new_rules = self.rule_builder(list(followed_users))
            await self.replace_rules(current_rules, new_rules)
            await self.bot.change_presence(
                activity=discord.Activity(name=f"{len(followed_users)} accounts", type=3)
            )


async def setup(bot: Siniara):
    await bot.add_cog(Streamer(bot))
