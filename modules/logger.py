import logging


def get_logger(logger_name):
    logger = logging.getLogger(logger_name)
    if logger.handlers:
        return logger

    # logger not created yet, assign options
    logger.setLevel(level=logging.INFO)
    fmt = logging.Formatter(
        fmt="{asctime} | {levelname:7} {name:>17} > {message}",
        style="{",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler = logging.StreamHandler()
    handler.setFormatter(fmt)
    logger.addHandler(handler)

    return logger
