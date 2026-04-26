import sys

from loguru import logger

logger.remove()
logger.add(
    sys.stdout,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name} | {message}",
    level="INFO",
    colorize=True,
)


def get_logger(name: str):
    return logger.bind(name=name)
