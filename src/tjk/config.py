from pydantic_settings import BaseSettings
from pathlib import Path
import os
import sys

def get_app_data_dir():
    """Get a writable directory for app data."""
    # Use User Home Directory
    home = Path.home()
    app_dir = home / ".tjk_v2"
    return app_dir

APP_DIR = get_app_data_dir()

class Settings(BaseSettings):
    BASE_URL: str = "https://www.tjk.org"
    LOG_LEVEL: str = "INFO"
    
    # DB Path - Relative path for portability
    DB_URL: str = "sqlite:///tjk.db"
    
    CACHE_DIR: Path = APP_DIR / "cache"
    SNAPSHOT_DIR: Path = APP_DIR / "snapshots"
    
    class Config:
        env_file = ".env"

settings = Settings()

# Ensure directories exist
try:
    settings.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    settings.SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
except Exception as e:
    print(f"Warning: Could not create cache dirs: {e}")
