# Siniara

Discord bot for realtime streaming tweets into discord channels. Now updated for Twitter API v2!

Any media is parsed and downloaded as discord files so it will never disappear in case the tweet is deleted.

Media options are configurable per server/channel/user, and non-media tweets can be ignored.

[Invite here!](https://discord.com/api/oauth2/authorize?client_id=523863343585296404&permissions=2147806272&scope=bot%20applications.commands)

* * *

## Deploying

1.  Clone this repository.
2.  Rename `.env.example` to `.env` and fill in your keys. You need a Twitter API v2 bearer token.

Deployment is very easy with docker compose.

    $ docker-compose build
    # docker-compose up

If you don't want to use docker, you can run the bot in your local environment.

1.  You need a running mariadb database. Apply the provided schema in `sql/schema.sql`
2.  Change `.env` database keys to point at your local database.

Tested with python 3.10.5, earlier versions might break.
    
    $ pip install -r requirements.txt
    $ python main.py
