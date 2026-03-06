"""
Scanwave CyberIntel Platform — Logging Configuration
=====================================================
Consistent log format across all modules.
Rotating file handler prevents unbounded log growth.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_configured = False


def setup_logging(name="scanwave", log_dir=None, level=logging.INFO):
    """Configure structured logging with rotating file handler.

    Args:
        name: Logger name (e.g. 'viewer', 'monitor', 'ai_agent')
        log_dir: Directory for log files (default: telegram_intel/)
        level: Log level (default: INFO)

    Returns:
        Configured logger instance
    """
    global _configured

    if log_dir is None:
        log_dir = Path("./telegram_intel")
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / f"{name}.log"

    # Format: timestamp [MODULE] LEVEL message
    fmt = "%(asctime)s [%(name)s] %(levelname)s %(message)s"
    date_fmt = "%Y-%m-%d %H:%M:%S"

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    # Rotating file handler: 10MB max, 5 backups
    file_handler = RotatingFileHandler(
        str(log_file), maxBytes=10 * 1024 * 1024, backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter(fmt, datefmt=date_fmt))
    logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(fmt, datefmt=date_fmt))
    logger.addHandler(console_handler)

    # Fix Windows encoding
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    if not _configured:
        _configured = True

    return logger
