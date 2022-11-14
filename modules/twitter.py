import asyncio
from dataclasses import dataclass
import io
from typing import Optional, Union

import arrow
import tweepy
import discord
from discord.app_commands import AppCommandError

from modules import queries
from modules.siniara import Siniara
from modules.ui import LinkButton

from loguru import logger

SendableChannel = Union[
    discord.VoiceChannel,
    discord.TextChannel,
    discord.Thread,
    discord.PartialMessageable,
]


class NoMedia(AppCommandError):
    pass


@dataclass
class TweetData:
    id: int
    author_id: int
    media: list
    screen_name: str
    url: str
    timestamp: arrow.Arrow
    text: str
    reply_to: Optional[str] = None


class TwitterRenderer:
    def __init__(self, bot):
        self.bot: Siniara = bot

    async def tweepy_tweet(self, tweet_id: int):
        response = await self.bot.tweepy.get_tweet(
            tweet_id,
            tweet_fields=["attachments", "created_at", "conversation_id", "entities"],
            expansions=["attachments.media_keys", "author_id"],
            media_fields=["variants", "url", "alt_text"],
            user_fields=["profile_image_url"],
        )

        tweet: tweepy.Tweet = response.data  # type: ignore

        # logger.info(tweet.data)
        # logger.info(response.includes)

        media = await self.tweepy_get_media(response)
        user = response.includes["users"][0]  # type: ignore
        screen_name = user.username
        tweet_url = f"https://twitter.com/{screen_name}/status/{tweet.id}"
        timestamp = arrow.get(tweet.created_at)
        tweet_text = self.expand_links(tweet.text, tweet.entities["urls"])
        reply_to = None
        if not tweet["conversation_id"] == tweet["id"]:
            reply_to = f"https://twitter.com/i/status/{tweet['conversation_id']}"

        return TweetData(
            int(tweet["id"]),
            tweet["author_id"],
            media,
            screen_name,
            tweet_url,
            timestamp,
            tweet_text,
            reply_to,
        )

    async def tweepy_get_media(self, response):
        media_urls = []
        media: tweepy.Media
        for media in response.includes.get("media", []):  # type: ignore
            if media.type == "photo":
                base, extension = media.url.rsplit(".", 1)
                media_urls.append(("jpg", base + "?format=" + extension + "&name=orig"))
            else:
                variants = sorted(
                    filter(lambda x: x["content_type"] == "video/mp4", media.data["variants"]),
                    key=lambda y: y["bit_rate"],
                    reverse=True,
                )
                media_urls.append(("mp4", variants[0]["url"]))

        return media_urls

    async def send_tweet(
        self,
        tweet_id: int,
        channels: list[SendableChannel],
        interaction: Optional[discord.Interaction] = None,
    ) -> None:
        """Format and send a tweet to given discord channels"""
        logger.info(f"sending {tweet_id} into {', '.join(f'#{c}' for c in channels)}")
        tweet = await self.tweepy_tweet(tweet_id)

        if tweet.id != tweet_id:
            logger.warning(f"Got id {tweet.id}, Possible retweet {tweet.url}")

        caption = (
            f"<:twitter:937425165241946162> **@{tweet.screen_name}**"
            f" <t:{tweet.timestamp.int_timestamp}:R>"
        )

        for channel in channels:
            if not channel.guild:
                continue

            tweet_config = await queries.tweet_config(self.bot.db, channel, tweet.author_id)
            content = discord.Embed(color=int("1ca1f1", 16))
            description = ""
            if tweet.reply_to:
                description += f"> [*replying to*]({tweet.reply_to})\n"

            if not tweet_config["media_only"] and tweet.text:
                description += tweet.text + "\n"

            content.description = description

            # discord normally has 8MB file size limit, but it can be increased in some guilds
            max_filesize = channel.guild.filesize_limit
            files, too_big_files = await self.download_files(tweet, max_filesize)

            if not files and not too_big_files and tweet_config["media_only"]:
                if interaction:
                    raise NoMedia

                return

            caption = "\n".join([caption] + too_big_files)
            button = LinkButton("View on Twitter", tweet.url)

            if (
                interaction
                and interaction.channel == channel
                and not interaction.extras.get("responded_once", False)
            ):
                await interaction.followup.send(
                    caption,
                    files=files,
                    embed=content if content.description else discord.utils.MISSING,
                    view=button,
                )
                interaction.extras["responded_once"] = True
            else:
                await channel.send(
                    caption,
                    files=files,
                    embed=content if content.description else discord.utils.MISSING,
                    view=button,
                )

    @staticmethod
    def expand_links(tweet_text: str, urls: list[dict]):
        results = []
        i = 0
        for replacement in urls:
            expanded_url = replacement["expanded_url"]
            if replacement.get("media_key") or replacement["display_url"].startswith(
                "twitter.com/i/web/status"
            ):
                # url is not relevant
                expanded_url = ""

            result = tweet_text[i : replacement["start"]]
            i = replacement["end"]
            if expanded_url:
                result += expanded_url
            results.append(result)

        return "".join(results).strip()

    async def download_files(
        self, tweet: TweetData, max_filesize: int
    ) -> tuple[list[discord.File], list[str]]:
        files = []
        too_big_files = []
        tasks = []
        for n, (extension, media_url) in enumerate(tweet.media, start=1):
            filename = f"{tweet.timestamp.format('YYMMDD')}-@{tweet.screen_name}-{tweet.id}-{n}.{extension}"
            tasks.append(self.download_media(media_url, filename, max_filesize))

        results = await asyncio.gather(*tasks)
        for result in results:
            if isinstance(result, discord.File):
                files.append(result)
            else:
                too_big_files.append(result)

        return files, too_big_files

    async def download_media(self, media_url: str, filename: str, max_filesize: int):
        async with self.bot.session.get(media_url) as response:
            if not response.ok:
                if response.headers.get("Content-Type") == "text/plain":
                    content = await response.text()
                    error_message = f"{response.status} {response.reason} | {content}"
                else:
                    error_message = f"{response.status} {response.reason}"

                logger.error(error_message)
                return f"`[{error_message}]`"

            content_length = response.headers.get("Content-Length") or response.headers.get(
                "x-full-image-content-length"
            )
            if content_length:
                if int(content_length) < max_filesize:
                    buffer = io.BytesIO(await response.read())
                    return discord.File(fp=buffer, filename=filename)
                elif int(content_length) >= max_filesize:
                    return media_url
            else:
                logger.warning(f"No content length header for {media_url}")
                # there is no Content-Length header
                # try to stream until we hit our limit
                try:
                    buffer = b""
                    async for chunk in response.content.iter_chunked(1024):
                        buffer += chunk
                        if len(buffer) > max_filesize:
                            raise ValueError
                    return discord.File(fp=io.BytesIO(buffer), filename=filename)
                except ValueError:
                    return media_url
