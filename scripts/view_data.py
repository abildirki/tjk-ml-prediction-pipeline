import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.tjk.storage.schema import RaceModel, EntryModel
from src.tjk.config import settings

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

def view_data():
    engine = create_engine(settings.DB_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    races = session.query(RaceModel).all()
    
    if not races:
        print("Veritabanında hiç yarış bulunamadı.")
        return

    print(f"\n=== VERİTABANI RAPORU ({len(races)} Yarış) ===\n")
    
    for race in races:
        print(f"🏁 {race.city} {race.race_no}. Koşu ({race.distance_m}m {race.surface})")
        print("-" * 80)
        print(f"{'No':<4} {'At Adı':<25} {'Jokey':<20} {'Kilo':<6} {'Derece':<10} {'Sıra':<4} {'Ganyan':<6}")
        print("-" * 80)
        
        for entry in race.entries:
            saddle = entry.saddle_no or '-'
            name = entry.horse_name
            jokey = entry.jockey_name or '-'
            weight = entry.weight_kg or '-'
            time = entry.finish_time or '-'
            rank = entry.rank or '-'
            ganyan = entry.ganyan or '-'
            
            print(f"{saddle:<4} {name:<25} {jokey:<20} {weight:<6} {time:<10} {rank:<4} {ganyan:<6}")
        print("\n")
        
    session.close()

if __name__ == "__main__":
    view_data()
