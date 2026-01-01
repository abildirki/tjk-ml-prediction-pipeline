import sys
import os
sys.path.append(os.path.join(os.getcwd(), "src"))

import asyncio
from datetime import date
from tjk.http.client import TJKClient
from tjk.parsers.program_parser import ProgramCsvParser

# Manual setup
TARGET_DATE = date(2025, 5, 5)
CITY = "Bursa"

async def debug_scrape():
    client = TJKClient()
    
    date_path = TARGET_DATE.strftime('%Y-%m-%d')
    date_file = TARGET_DATE.strftime('%d.%m.%Y')
    year = TARGET_DATE.year
    
    normalized_city = CITY
    
    url = f"https://medya-cdn.tjk.org/raporftp/TJKPDF/{year}/{date_path}/CSV/GunlukYarisProgrami/{date_file}-{normalized_city}-GunlukYarisProgrami-TR.csv"
    print(f"DEBUG URL: {url}")
    
    try:
        content = await client.get(url)
        print(f"Content Length: {len(content)}")
        print(f"First line: {content.splitlines()[0]}")
        
        parser = ProgramCsvParser()
        races = parser.parse_csv(content, TARGET_DATE, CITY)
        print(f"Parsed Races: {len(races)}")
        if races:
            print(f"First Race Entries: {len(races[0].entries)}")
            print(f"First Entry Name: {races[0].entries[0].horse_name}")
            print(f"First Entry AGF: {races[0].entries[0].agf}")
            print(f"First Entry Sire: {races[0].entries[0]._temp_horse_info.get('sire')}")
            
    except Exception as e:
        print(f"Error: {e}")
        
    await client.close()

if __name__ == "__main__":
    asyncio.run(debug_scrape())
