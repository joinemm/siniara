import os


class Config:
    def __init__(self):
        self.owner_id = 133311691852218378
        self.prefix = "$"
        self.guild_follow_limit = 25
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
