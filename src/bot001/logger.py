"""日志配置"""

from __future__ import annotations

import logging
import sys


def setup_logger(name: str = "bot001", level: int = logging.INFO) -> logging.Logger:
    """配置并返回 logger 实例"""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(level)

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger
