#!/usr/bin/env python3
# BY: HACK UNDERWAY - Suite OSINT Completa
# Version 2.0 with interactive menu, batch processing, caching, and more
#
# This is the main entry point. It imports the modularized components from src/.

import os
import sys

# Ensure the project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup logging with file rotation before any other imports
import logging
from logging.handlers import RotatingFileHandler

from src.config import LOG_FILE, LOG_LEVEL

# Ensure logs directory exists
log_dir = os.path.dirname(LOG_FILE)
if log_dir and not os.path.exists(log_dir):
    os.makedirs(log_dir, exist_ok=True)

# Configure root logger with file rotation
root_logger = logging.getLogger()
root_logger.setLevel(LOG_LEVEL)

# File handler with rotation (5 MB max, 3 backups)
try:
    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    root_logger.addHandler(file_handler)
except Exception as e:
    print(f"Warning: Could not set up file logging: {e}")

# Console handler (WARNING and above)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.WARNING)
console_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
root_logger.addHandler(console_handler)

# Import and run main
from src.menu import main  # noqa: E402

if __name__ == "__main__":
    main()
