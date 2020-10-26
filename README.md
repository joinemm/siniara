## Fansite Bot

Discord bot for realtime streaming tweets to discord channels.
Mostly focused on kpop fansites but works just fine for any twitter user.



I offer a public bot that's running the service. Feel free to invite it by clicking [here](https://discord.com/api/oauth2/authorize?client_id=523863343585296404&permissions=322624&scope=bot)

---

Optionally you can also run your own instance of the bot.

> These instructions assume you already have a local MariaDB instance running!

Get the source code and setup python environment:
```
$ git clone https://joinemm/fansite-bot
$ cd fansite-bot
$ python -m venv venv
$ source venv/bin/activate
$ pip install -r requirements.txt
```

Fill out the `config.toml.example` with your own values and rename it to `config.toml`.

Build the database schema:
```
$ mysql fansitebot < sql/schema.sql
```

If everything went good you should be able to run the bot now:

```
$ python main.py
```