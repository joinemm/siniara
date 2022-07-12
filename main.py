import signal

import uvloop
from dotenv import load_dotenv

from modules.siniara import Siniara

load_dotenv()
uvloop.install()


# Docker by default sends a SIGTERM to a container
# and waits 10 seconds for it to stop before killing it with a SIGKILL.
# This makes ctrl-c work as normal even in a docker container.
def handle_sigterm(*args):
    raise KeyboardInterrupt(*args)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, handle_sigterm)
    bot = Siniara()
    bot.run(bot.config.discord_token)
