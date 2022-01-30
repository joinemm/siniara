# Siniara

Discord bot for realtime streaming tweet media to discord channels.    
Mostly focused on kpop fansites but works just fine for any twitter accounts that post a lot of images.
Configurable media options per user/channel/server.

[Invite link](https://discord.com/api/oauth2/authorize?client_id=523863343585296404&permissions=322624&scope=bot)

---

## Deploying

You can run your own instance of the bot very easily by using the included `docker-compose.yml` configuration. (must have docker and docker-compose installed)

1. Clone this repository.
2. Rename `config.toml.example` to `config.toml` and fill it with your own api keys.
3. `$ docker-compose up`
