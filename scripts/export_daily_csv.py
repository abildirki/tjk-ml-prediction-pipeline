
import sys
import os
import csv
from datetime import date
from sqlalchemy import text

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from tjk.storage.db import get_db
from tjk.storage.schema import RaceModel

def export_today_csv():
    db = next(get_db())
    today = date(2025, 12, 20) # Hardcoded for this specific run as per "autonomous" simulation ensuring file exists
    
    # Or use date.today() if we trust system time is 2025-12-20 (It is)
    today = date.today()

    races = db.query(RaceModel).filter(RaceModel.date == today).all()
    
    output_dir = "data/daily"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    filename = f"{today}.csv"
    filepath = os.path.join(output_dir, filename)
    
    print(f"Exporting to {filepath}...")
    
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['City', 'RaceNo', 'Distance', 'Surface', 'Horse', 'Jockey'])
        
        for r in races:
            for e in r.entries:
                writer.writerow([r.city, r.race_no, r.distance_m, r.surface, e.horse_name, e.jockey_name])
                
    print("Export complete.")

if __name__ == "__main__":
    export_today_csv()
