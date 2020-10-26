import logging
import coloredlogs


def get_logger(name):
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    fh = logging.FileHandler(".error.log")
    fh.setLevel(logging.ERROR)
    logger.addHandler(fh)

    # logger not created yet, assign options
    coloredlogs.install(
        fmt="[{asctime}.{msecs:03.0f}] {message}",
        style="{",
        level="DEBUG",
        logger=logger,
    )

    return logger
