"""Configuration for Picoripi Companion Server."""
import os
from pathlib import Path
from typing import List

# Server host and port
DEFAULT_PORT = int(os.environ.get("COMPANION_PORT", "8000"))
DEFAULT_HOST = os.environ.get("COMPANION_HOST", "0.0.0.0")

# Auth token / PIN for securing API access
# By default, reads PICORIPI_COMPANION_TOKEN or falls back to 'picoripi'
AUTH_TOKEN = os.environ.get("PICORIPI_COMPANION_TOKEN", "picoripi")

# Data directory where projects, glossaries and occurrences are stored
DEFAULT_DATA_DIR = Path(os.environ.get("COMPANION_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))

# Web static files directory
WEB_DIR = Path(__file__).resolve().parent.parent / "web"

# CORS origins
CORS_ORIGINS: List[str] = ["*"]
