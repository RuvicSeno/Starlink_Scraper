"""
Centralized configuration module.
Loads settings from .env file with sensible defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Project root is one level up from this file's directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load .env from project root
load_dotenv(PROJECT_ROOT / ".env")


class Settings:
    """Application settings loaded from environment variables."""

    # Starlink target URL
    STARLINK_URL: str = os.getenv(
        "STARLINK_URL",
        "https://starlink.com/account/service-line/AST-2293597-46342-54"
        "?selectedDevice=ut01000000-00000000-0060d786&page=0&limit=5"
    )

    # Server configuration
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8000"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    SCRAPER_DEBUG: bool = os.getenv("SCRAPER_DEBUG", "1").lower() in ("1", "true", "yes", "on")

    # Database — file path relative to project root
    DATABASE_PATH: Path = PROJECT_ROOT / os.getenv("DATABASE_PATH", "data/starlink.db")

    # Session storage for Playwright cookies
    SESSION_DIR: Path = PROJECT_ROOT / os.getenv("SESSION_DIR", "data/session")

    # Derived paths
    FRONTEND_DIR: Path = PROJECT_ROOT / "frontend"
    DATA_DIR: Path = PROJECT_ROOT / "data"
    DEBUG_DIR: Path = PROJECT_ROOT / "data" / "debug"

    def ensure_directories(self) -> None:
        """Create required directories if they don't exist."""
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.SESSION_DIR.mkdir(parents=True, exist_ok=True)
        self.DEBUG_DIR.mkdir(parents=True, exist_ok=True)


# Singleton instance
settings = Settings()
