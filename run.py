"""
Convenience startup script for the Starlink Usage Scraper.
Run with: python run.py
"""

import sys
import shutil


def check_dependencies():
    """Verify required packages are installed."""
    missing = []
    for package in ["fastapi", "uvicorn", "playwright", "aiosqlite", "dotenv"]:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)

    if missing:
        print("=" * 50)
        print("Missing dependencies detected!")
        print("Please install requirements first:")
        print("  pip install -r requirements.txt")
        print("  playwright install chromium")
        print("=" * 50)
        sys.exit(1)


def check_env():
    """Check if .env file exists, create from example if not."""
    from pathlib import Path
    env_path = Path(__file__).parent / ".env"
    example_path = Path(__file__).parent / ".env.example"

    if not env_path.exists() and example_path.exists():
        shutil.copy(example_path, env_path)
        print("Created .env from .env.example — review and update if needed.")


def main():
    """Start the application."""
    check_dependencies()
    check_env()

    import uvicorn
    from backend.config import settings

    print("=" * 50)
    print("  Starlink Usage Scraper & Dashboard")
    print(f"  Starting at http://{settings.HOST}:{settings.PORT}")
    print("=" * 50)

    uvicorn.run(
        "backend.app:app",
        host=settings.HOST,
        port=settings.PORT,
        log_level=settings.LOG_LEVEL.lower(),
        reload=False
    )


if __name__ == "__main__":
    main()
