import logging
from logging.handlers import RotatingFileHandler
import os

os.makedirs("logs", exist_ok=True)

error_logger = logging.getLogger("error_logger")
error_logger.setLevel(logging.ERROR)

file_handler = RotatingFileHandler(
    "logs/errors.log", maxBytes=5_000_000, backupCount=3
)

formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)
file_handler.setFormatter(formatter)

error_logger.addHandler(file_handler)