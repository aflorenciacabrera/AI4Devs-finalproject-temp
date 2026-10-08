"""Registro de actividad: archivo con rotación, sin PIN, firmas ni hashes completos."""

import logging
import logging.handlers
import sys
from pathlib import Path

LOG_NAME = "firmadoc_agent"
MAX_BYTES = 1024 * 1024
BACKUP_COUNT = 3
FORMAT = "%(asctime)s %(levelname)s %(message)s"


def setup_logging(level: str, log_file: Path) -> logging.Logger:
    logger = logging.getLogger(LOG_NAME)
    logger.setLevel(level)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter(FORMAT))
    logger.addHandler(file_handler)
    if sys.stderr is not None:  # con --noconsole (PyInstaller) no hay stderr
        stream = logging.StreamHandler(sys.stderr)
        stream.setFormatter(logging.Formatter(FORMAT))
        logger.addHandler(stream)
    logger.propagate = False
    return logger
