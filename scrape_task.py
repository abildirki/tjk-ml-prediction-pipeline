
import asyncio
import sys
import os
from datetime import date

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from tjk.cli import scrape_range_async

async def main():
    # Scrape 19.12.2025 to 20.12.2025
    start = date(2025, 12, 19)
    end = date(2025, 12, 20)
    
    print(f"Starting scrape for {start} to {end}...")
    await scrape_range_async(start, end)
    print("Scrape completed.")

if __name__ == "__main__":
    asyncio.run(main())
