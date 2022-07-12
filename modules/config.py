import os

import modules.logger as log

logger = log.get_logger(__name__)


class Config:
    def __init__(self):
        try:
            self.owner_id = 133311691852218378
            self.prefix = "$"
            self.guild_follow_limit = 20
            self.guild_unlocked_follow_limit = 100

            self.discord_token = os.environ["DISCORD_TOKEN"]
            self.twitter_bearer_token = os.environ["TWITTER_BEARER_TOKEN"]
            self.dbcredentials = {
                "host": os.environ.get("DB_HOST", "localhost"),
                "port": int(os.environ["DB_PORT"]),
                "user": os.environ["DB_USER"],
                "password": os.environ["DB_PASS"],
                "db": os.environ["DB_NAME"],
            }
        except KeyError as e:
            logger.error("Error parsing config file. Something must be missing.")
            logger.error(e)
            quit()
