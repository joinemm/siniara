# Siniara

Discord bot for realtime streaming tweets into discord channels. Now updated for Twitter API v2!

Any media is parsed and downloaded as discord files so it will never disappear in case the tweet is deleted.

Media options are configurable per server/channel/user, and non-media tweets can be ignored.

[Invite here!](https://discord.com/api/oauth2/authorize?client_id=523863343585296404&permissions=322624&scope=bot)

* * *

## Deploying

You can run your own instance of the bot very easily by using the included `docker-compose.yml` configuration.

1.  Clone this repository.
2.  Rename `.env.example` to `.env` and fill in your tokens.
3.  `$ docker-compose up`
