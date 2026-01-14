
import sys
import os
from datetime import date
from sqlalchemy import text, func
from sqlalchemy.orm import joinedload

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from tjk.storage.db import get_db
from tjk.storage.schema import RaceModel, EntryModel

def calculate_score(entry, history_stats):
    score = 0
    
    # 1. Handicap Points
    if entry.hp:
        score += entry.hp * 0.5
        
    # 2. Form Score
    if entry.form_score:
        form_points = 0
        try:
            for char in str(entry.form_score):
                if char == '1': form_points += 10
                elif char == '2': form_points += 6
                elif char == '3': form_points += 3
                elif char == '4': form_points += 1
            score += form_points
        except: 
            pass
    
    # 3. AGF
    if entry.agf:
        score += entry.agf * 2.0
        
    # 4. Historical Performance
    stats = history_stats.get(entry.horse_name)
    if stats:
        avg_rank = stats['avg_rank']
        if stats['count'] > 0:
            rank_bonus = max(0, (15 - avg_rank) * 3)
            score += rank_bonus
            
    return score

def predict_day():
    db = next(get_db())
    today = date(2025, 12, 20)
    
    output_path = "prediction_20_12_2025.md"
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"# Prediction for {today}\n\n")
            
            races = db.query(RaceModel).filter(
                RaceModel.date == today
            ).order_by(RaceModel.city, RaceModel.race_no).all()
            
            if not races:
                f.write("No races found for this date. (Did you scrape?)\n")
                print("No races found.")
                return

            city_races = {}
            for r in races:
                if r.city not in city_races: city_races[r.city] = []
                city_races[r.city].append(r)
                
            for city, racing_list in city_races.items():
                f.write(f"\n## {city}\n\n")
                for race in racing_list:
                    f.write(f"### Race {race.race_no} - {race.distance_m}m {race.surface}\n")
                    f.write("| Rank | Horse | Jockey | HP | Form | Score |\n")
                    f.write("|---|---|---|---|---|---|\n")
                    
                    candidates = []
                    for entry in race.entries:
                        avg_rank = db.query(func.avg(EntryModel.rank)).filter(
                            EntryModel.horse_name == entry.horse_name,
                            EntryModel.rank != None
                        ).scalar() or 10.0
                        
                        count = db.query(func.count(EntryModel.id)).filter(
                            EntryModel.horse_name == entry.horse_name,
                            EntryModel.rank != None
                        ).scalar()
                        
                        stats = {'avg_rank': avg_rank, 'count': count}
                        score = calculate_score(entry, {entry.horse_name: stats})
                        candidates.append((entry, score, stats))
                        
                    candidates.sort(key=lambda x: x[1], reverse=True)
                    
                    for i, (e, score, stat) in enumerate(candidates[:6]):
                        f.write(f"| {i+1} | {e.horse_name} | {e.jockey_name} | {e.hp or '-'} | {e.form_score or '-'} | {score:.1f} |\n")
                    f.write("\n")
        print(f"Prediction saved to {output_path}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    predict_day()
