"""
Configuration module for SearchPhone OSINT tool.
Loads environment variables, config.json, and provides default settings.
"""

import json
import logging
import os

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Try to load config
CONFIG_FILE = "config.json"
CONFIG = {}
if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            CONFIG = json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load config: {e}")

DEFAULT_CONFIG = {
    "settings": {
        "default_region": "pe",
        "max_workers": 6,
        "request_timeout": 15,
        "retry_attempts": 3,
        "retry_delay": 2,
        "cache_enabled": True,
        "cache_dir": "cache",
        "cache_max_age_days": 7,
        "export_formats": ["json", "pdf", "csv"],
        "user_agent": "SearchPhone/2.0 OSINT Tool",
        "log_file": "logs/searchphone.log",
        "log_level": "WARNING",
        "http_proxy": "",
        "https_proxy": "",
    },
    "search": {
        "google": {"enabled": True, "max_results": 20},
        "duckduckgo": {"enabled": True, "max_results": 10},
        "reddit": {"enabled": True, "max_results": 20},
        "github": {"enabled": True, "max_results": 10},
        "twitter": {"enabled": True, "max_results": 15},
        "vk": {"enabled": True, "max_results": 10},
        "telegram": {"enabled": True, "max_results": 10},
    },
}

# Merge config with defaults
for key, value in DEFAULT_CONFIG.items():
    if key not in CONFIG:
        CONFIG[key] = value

SETTINGS = CONFIG.get("settings", DEFAULT_CONFIG["settings"])
SEARCH_CONFIG = CONFIG.get("search", DEFAULT_CONFIG["search"])
REQUEST_TIMEOUT = SETTINGS.get("request_timeout", 15)
RETRY_ATTEMPTS = SETTINGS.get("retry_attempts", 3)
RETRY_DELAY = SETTINGS.get("retry_delay", 2)
CACHE_ENABLED = SETTINGS.get("cache_enabled", True)
CACHE_DIR = SETTINGS.get("cache_dir", "cache")
CACHE_MAX_AGE_DAYS = SETTINGS.get("cache_max_age_days", 7)

# Proxy settings
HTTP_PROXY = SETTINGS.get("http_proxy", "") or os.getenv("HTTP_PROXY", "")
HTTPS_PROXY = SETTINGS.get("https_proxy", "") or os.getenv("HTTPS_PROXY", "")
PROXIES = {}
if HTTP_PROXY:
    PROXIES["http"] = HTTP_PROXY
if HTTPS_PROXY:
    PROXIES["https"] = HTTPS_PROXY

# Log file settings
LOG_FILE = SETTINGS.get("log_file", "logs/searchphone.log")
LOG_LEVEL = getattr(logging, SETTINGS.get("log_level", "WARNING").upper(), logging.WARNING)

if CACHE_ENABLED and not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)
