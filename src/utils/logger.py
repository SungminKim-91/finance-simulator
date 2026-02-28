"""로깅 설정"""
import logging
import sys
from datetime import datetime
from pathlib import Path

from config.settings import LOG_DIR


def setup_logger(
    name: str,
    level: str = "INFO",
    log_to_file: bool = True,
) -> logging.Logger:
    """
    로거 생성.

    Format: [2026-03-01 10:30:00] [INFO] [module_name] message
    File: data/logs/pipeline_{date}.log
    Console: 동시 출력
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler
    if log_to_file:
        log_file = LOG_DIR / f"pipeline_{datetime.now().strftime('%Y-%m-%d')}.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
