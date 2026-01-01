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
    
    # DB Path - also move to App Data if strictly needed, but letting it stay hardcoded for now 
    # unless requested. However, if EXE moves, DB path implies hard dependency on that path.
    # The existing config has absolute path: r"sqlite:///C:\Users\Ali\Desktop\tjk\tjk_v2\tjk.db"
    # This is fine for now on this specific machine.
    DB_URL: str = r"sqlite:///C:\Users\Ali\Desktop\tjk\tjk_v2\tjk.db"
    
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
