
import sys
import os
from datetime import date
from sqlalchemy import text

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from tjk.storage.db import get_db
from tjk.storage.schema import RaceModel, EntryModel

def check_race_4():
    db = next(get_db())
    today = date(2025, 12, 20)
    
    race = db.query(RaceModel).filter(
        RaceModel.date == today,
        RaceModel.city == "Adana",
        RaceModel.race_no == 4
    ).first()
    
    if not race:
        print("Race 4 not found.")
        return

    print(f"Race 4: {race.distance_m}m {race.surface}")
    
    entries = sorted(race.entries, key=lambda x: x.rank if x.rank else 999)
    
    print(f"{'Rank':<5} {'Horse':<20} {'Jockey':<15} {'Score'} (Our Rank in Prediction)")
    print("-" * 60)
    
    # We need to reconstruct our prediction order to see where the winner was
    # This is rough as score logic is in predict_task.py but we can look at the name
    
    for e in entries:
        if e.rank:
            print(f"{e.rank:<5} {e.horse_name:<20} {e.jockey_name:<15}")

if __name__ == "__main__":
    check_race_4()
