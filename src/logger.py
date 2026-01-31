"""
Logging configuration for TwitchTranslateBOT
Provides centralized logging setup with daily rotating file handler.
"""
import logging
import sys
from pathlib import Path
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler


def _get_log_directory() -> Path:
    """
    Get the appropriate log directory based on execution context.

    Returns:
        Path to the log directory
    """
    if getattr(sys, 'frozen', False):
        # Running as exe (PyInstaller)
        base_dir = Path(sys.executable).parent
    else:
        # Running as script (development)
        base_dir = Path(__file__).parent.parent / "dist"

    return base_dir / "logs"


def setup_logger(name: str = "TwitchTranslateBOT", level: str = "INFO") -> logging.Logger:
    """
    Setup and configure logger with daily rotating file handler.
    Console output is disabled - all logs go to file only.

    Args:
        name: Logger name
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Prevent duplicate handlers if logger already exists
    if logger.handlers:
        return logger

    # Set logging level
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(logging.DEBUG)  # Logger itself captures all levels

    # Create logs directory if it doesn't exist
    log_dir = _get_log_directory()
    log_dir.mkdir(parents=True, exist_ok=True)

    # Daily rotating file handler
    # File format: bot_YYYY-MM-DD.log
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = log_dir / f"bot_{today}.log"

    file_handler = TimedRotatingFileHandler(
        log_file,
        when='midnight',      # Rotate at midnight
        interval=1,           # Every 1 day
        backupCount=7,        # Keep 7 days of logs
        encoding='utf-8'
    )
    # Set suffix for rotated files (e.g., bot_2026-01-28.log.2026-01-27)
    file_handler.suffix = "%Y-%m-%d"
    file_handler.setLevel(logging.DEBUG)

    file_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)

    # Add only file handler (no console output)
    logger.addHandler(file_handler)

    return logger


def set_log_level(level: str) -> None:
    """
    ログレベルを動的に変更する

    Args:
        level: ログレベル (DEBUG, INFO, WARNING, ERROR)
    """
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
    }
    log_level = level_map.get(level.upper(), logging.INFO)

    # ルートロガーとすべてのハンドラのレベルを変更
    root_logger = logging.getLogger("TwitchTranslateBOT")
    root_logger.setLevel(log_level)

    for handler in root_logger.handlers:
        handler.setLevel(log_level)

    root_logger.info(f"Log level changed to: {level.upper()}")


def get_log_level() -> str:
    """
    現在のログレベルを取得する

    Returns:
        現在のログレベル文字列
    """
    level_names = {
        logging.DEBUG: "DEBUG",
        logging.INFO: "INFO",
        logging.WARNING: "WARNING",
        logging.ERROR: "ERROR",
    }
    root_logger = logging.getLogger("TwitchTranslateBOT")
    return level_names.get(root_logger.level, "INFO")


# Create default logger instance
logger = setup_logger()
