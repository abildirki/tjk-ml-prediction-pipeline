import asyncio
import sys
import os
from datetime import date

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from tjk.cli import scrape_range_async

async def main():
    # Scrape TODAY (2025-12-21) specifically
    target = date(2025, 12, 21)
    
    print(f"🚀 Force Scraping for {target}...")
    await scrape_range_async(target, target)
    print("✅ Force Scrape completed.")

if __name__ == "__main__":
    asyncio.run(main())
