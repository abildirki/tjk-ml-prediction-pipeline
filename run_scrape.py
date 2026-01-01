import asyncio
import sys
import os
from datetime import date, timedelta

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from tjk.cli import scrape_range_async
from tjk.storage.db import get_db
from sqlalchemy import text

async def main():
    # 1. Determine Start Date (Last recorded date in DB or default)
    db = next(get_db())
    try:
        last_date_str = db.execute(text("SELECT max(date) FROM races")).scalar()
    except Exception:
        last_date_str = None
    
    if last_date_str:
        # Start from the last date found (to verify/update results for that day)
        start = date.fromisoformat(last_date_str)
        print(f"Found existing data up to {start}. Resuming scrape from there...")
    else:
        # Default start if DB is empty
        start = date(2025, 5, 5)
        print("Database empty. Starting fresh from 2025-05-05...")

    # 2. End Date: Today
    end = date.today()
    
    if start > end:
        print("Database is already up to date!")
        return

    await scrape_range_async(start, end)

if __name__ == "__main__":
    asyncio.run(main())
