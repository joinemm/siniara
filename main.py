import logging
import signal
import sys

import uvloop
from dotenv import load_dotenv

from modules.siniara import Siniara
from loguru import logger

load_dotenv()
uvloop.install()


class InterceptHandler(logging.Handler):
    def emit(self, record):
        # Get corresponding Loguru level if it exists.
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message.
        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


logging.basicConfig(handlers=[InterceptHandler()], level=1, force=True)


# Docker by default sends a SIGTERM to a container
# and waits 10 seconds for it to stop before killing it with a SIGKILL.
# This makes ctrl-c work as normal even in a docker container.
def handle_sigterm(*args):
    raise KeyboardInterrupt(*args)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, handle_sigterm)
    bot = Siniara()
    bot.run(bot.config.discord_token, root_logger=True)
