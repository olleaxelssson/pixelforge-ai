"""Application-wide logging configuration."""

import logging
import sys


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
    root = logging.getLogger("pixelforge")
    root.setLevel(level)
    if not root.handlers:
        root.addHandler(handler)
