import sys
import os
sys.path.append(os.path.join(os.getcwd(), "src"))

import asyncio
from datetime import date
from tjk.http.client import TJKClient
from tjk.parsers.program_parser import ProgramParser
from tjk.config import settings

async def debug_discovery():
    client = TJKClient()
    parser = ProgramParser()
    
    target_date = date(2025, 5, 5)
    url = f"{settings.BASE_URL}/TR/YarisSever/Info/Page/GunlukYarisProgrami?QueryParameter_Tarih={target_date.strftime('%d/%m/%Y')}"
    print(f"Fetching: {url}")
    
    html = await client.get(url)
    print(f"HTML Length: {len(html)}")
    
    cities = parser.parse_cities(html)
    print(f"Found Cities: {[c['name'] for c in cities]}")
    
    # Dump HTML to file for inspection if needed
    with open("debug_page.html", "w", encoding="utf-8") as f:
        f.write(html)
        
    await client.close()

if __name__ == "__main__":
    asyncio.run(debug_discovery())
