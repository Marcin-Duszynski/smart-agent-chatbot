"""
Configuration settings for Nova Act browser automation
Self-contained configuration for Docker deployment
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file (suppress warnings if not found)
load_dotenv(verbose=False)

# Nova Act API Key (Required)
NOVA_ACT_API_KEY = os.environ.get("NOVA_ACT_API_KEY")
if not NOVA_ACT_API_KEY:
    print("Warning: NOVA_ACT_API_KEY not found in environment variables")

# Browser settings - Core
BROWSER_HEADLESS = os.environ.get("NOVA_BROWSER_HEADLESS", "True").lower() in ("true", "1", "yes")
BROWSER_START_URL = "https://www.google.com"  # Default starting URL
BROWSER_MAX_STEPS = int(os.environ.get("NOVA_BROWSER_MAX_STEPS", "3"))  # Maximum turns between Nova Act and Browser
BROWSER_TIMEOUT = int(os.environ.get("NOVA_BROWSER_TIMEOUT", "30"))
BROWSER_URL_TIMEOUT = int(os.environ.get("NOVA_BROWSER_URL_TIMEOUT", "10"))
LOGS_DIRECTORY = os.environ.get("NOVA_BROWSER_LOGS_DIR", None)
BROWSER_RECORD_VIDEO = os.environ.get("NOVA_BROWSER_RECORD_VIDEO", "False").lower() in ("true", "1", "yes")
BROWSER_QUIET_MODE = os.environ.get("NOVA_BROWSER_QUIET", "False").lower() in ("true", "1", "yes")
BROWSER_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
BROWSER_USER_DATA_DIR = os.environ.get("NOVA_BROWSER_USER_DATA_DIR", "/tmp/nova_browser_profiles/base")
BROWSER_CLONE_USER_DATA = os.environ.get("NOVA_BROWSER_CLONE_USER_DATA", "True").lower() in ("true", "1", "yes")
BROWSER_SCREENSHOT_QUALITY = int(os.environ.get("NOVA_BROWSER_SCREENSHOT_QUALITY", "70"))
BROWSER_SCREENSHOT_MAX_WIDTH = int(os.environ.get("NOVA_BROWSER_SCREENSHOT_MAX_WIDTH", "800"))

# MCP server settings
MCP_SERVER_NAME = "nova-browser-automation"
MCP_VERSION = "0.1.0"
MCP_TRANSPORT = os.environ.get("NOVA_MCP_TRANSPORT", "streamable-http")
MCP_PORT = int(os.environ.get("NOVA_MCP_PORT", "8000"))
MCP_HOST = os.environ.get("NOVA_MCP_HOST", "0.0.0.0")
MCP_LOG_LEVEL = os.environ.get("NOVA_MCP_LOG_LEVEL", "INFO")

# Default browser settings
DEFAULT_BROWSER_SETTINGS = {
    # Browser display settings
    "headless": BROWSER_HEADLESS,
    "start_url": BROWSER_START_URL,
    
    # Performance and timeout settings
    "max_steps": BROWSER_MAX_STEPS,
    "timeout": BROWSER_TIMEOUT,
    "go_to_url_timeout": BROWSER_URL_TIMEOUT,
    
    # Logging and debugging
    "logs_directory": LOGS_DIRECTORY,
    "record_video": BROWSER_RECORD_VIDEO,
    "quiet": BROWSER_QUIET_MODE,
    
    # User agent and authentication settings
    "user_agent": BROWSER_USER_AGENT,
    
    # Browser profile settings (for authentication)
    "user_data_dir": BROWSER_USER_DATA_DIR,
    "clone_user_data_dir": BROWSER_CLONE_USER_DATA,
    
    # Screenshot settings
    "screenshot_quality": BROWSER_SCREENSHOT_QUALITY,
    "screenshot_max_width": BROWSER_SCREENSHOT_MAX_WIDTH,
}

# MCP server settings
MCP_SERVER_SETTINGS = {
    "server_name": MCP_SERVER_NAME,
    "version": MCP_VERSION,
    "transport": MCP_TRANSPORT,
    "port": MCP_PORT,
    "host": MCP_HOST,
    "log_level": MCP_LOG_LEVEL,
}

# Nova Act settings
NOVA_ACT_SETTINGS = {
    "api_key": NOVA_ACT_API_KEY,
    "headless": BROWSER_HEADLESS,
    "timeout": BROWSER_TIMEOUT,
}