"""
Application configuration.

Centralizes all configurable parameters so they can be overridden
via environment variables without touching code.
"""

import os


# How many seconds of silence before a device is considered OFFLINE.
DEVICE_TIMEOUT_SECONDS: int = int(os.getenv("DEVICE_TIMEOUT_SECONDS", "30"))

# Server configuration
HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8000"))
