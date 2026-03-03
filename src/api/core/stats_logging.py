import logging
from logging.handlers import RotatingFileHandler

stats_logger = logging.getLogger("stats_logger")
stats_logger.setLevel(logging.INFO)

file_handler = RotatingFileHandler(
    "logs/stats.log", maxBytes=5_000_000, backupCount=3
)

formatter = logging.Formatter(
    '{"time":"%(asctime)s","route":"%(route)s","method":"%(method)s","status":%(status)d,"duration_ms":%(duration).2f}'
)
file_handler.setFormatter(formatter)

stats_logger.addHandler(file_handler)