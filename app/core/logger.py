import logging
import os
from typing import Any

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)


class LevelFilter(logging.Filter):
    def __init__(self, low: int, high: int) -> None:
        super().__init__()
        self.low = low
        self.high = high

    def filter(self, record: logging.LogRecord) -> bool:
        return self.low <= record.levelno <= self.high


def setup_logging() -> None:
    formatter: logging.Formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%d-%m-%Y %H:%M:%S",
    )

    # === FILE HANDLER: progress.log (INFO até WARNING) ===
    progress_handler: logging.FileHandler = logging.FileHandler(
        f"{LOG_DIR}/app.log", mode="a"
    )
    progress_handler.setLevel(logging.INFO)
    progress_handler.addFilter(LevelFilter(logging.INFO, logging.WARNING))
    progress_handler.setFormatter(formatter)

    # === FILE HANDLER: errors.log (ERROR e CRITICAL) ===
    error_handler: logging.FileHandler = logging.FileHandler(
        f"{LOG_DIR}/errors.log", mode="a"
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.addFilter(LevelFilter(logging.ERROR, logging.CRITICAL))
    error_handler.setFormatter(formatter)

    # === CONSOLE HANDLER ===
    console_handler: logging.StreamHandler[Any] = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # === ROOT LOGGER ===
    logger: logging.Logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(progress_handler)
    logger.addHandler(error_handler)
    logger.addHandler(console_handler)
