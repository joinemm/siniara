import toml
import modules.logger as log

logger = log.get_logger(__name__)


class Config:
    def __init__(self, filename):
        self.json = toml.load(filename)
        self.validate_config()

    def quit_on_empty(self, value):
        if value is None or value == "":
            logger.error("Error parsing config file. One of the values is empty.")
            quit()
        else:
            return value

    def validate_config(self):
        try:
            self.owner_id = self.quit_on_empty(self.json["owner_id"])
            self.prefix = self.quit_on_empty(self.json["prefix"])
            self.discord_token = self.quit_on_empty(self.json["keys"]["discord_token"])
            self.statcord_token = self.json["keys"].get("discord_token")
            self.twitter_consumer_key = self.quit_on_empty(
                self.json["keys"]["twitter"]["consumer_key"]
            )
            self.twitter_consumer_secret = self.quit_on_empty(
                self.json["keys"]["twitter"]["consumer_secret"]
            )
            self.twitter_access_token = self.quit_on_empty(
                self.json["keys"]["twitter"]["access_token"]
            )
            self.twitter_access_secret = self.quit_on_empty(
                self.json["keys"]["twitter"]["access_secret"]
            )
            self.dbcredentials = self.quit_on_empty(self.json["database"])
            self.guild_follow_limit = self.quit_on_empty(self.json["guild_follow_limit"])
            self.guild_unlocked_follow_limit = self.quit_on_empty(
                self.json["guild_unlocked_follow_limit"]
            )
        except KeyError as e:
            logger.error("Error parsing config file. Something must be missing.")
            logger.error(e)
            quit()
