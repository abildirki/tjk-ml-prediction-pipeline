import sys
import os
from datetime import date
from sqlalchemy import text, func
from sqlalchemy.orm import joinedload
sys.path.append(os.path.join(os.getcwd(), "src"))

from tjk.storage.db import get_db
from tjk.storage.schema import RaceModel, EntryModel, HorseModel
from tjk.models.race import SurfaceType

def calculate_score(entry, history_stats):
    score = 0
    
    # 1. Handicap Points (Base Class)
    if entry.hp:
        score += entry.hp * 0.5
        
    # 2. Form Score (Recent Form) - "121112"
    if entry.form_score:
        # Give points for recent good performance
        # 1 -> 15 pts, 2 -> 10 pts, 3 -> 5 pts, 4 -> 3 pts
        form_points = 0
        try:
            # Reverse string to value recent races more? 
            # Usually strict right is most recent? The string is like "121112".
            # Let's just count totals for now to be robust.
            for char in str(entry.form_score):
                if char == '1': form_points += 10
                elif char == '2': form_points += 6
                elif char == '3': form_points += 3
                elif char == '4': form_points += 1
            
            # Cap realistic form bonus to not outweigh HP entirely
            score += form_points
        except: 
            pass
    
    # 3. AGF (Six Ganyan Favorisi) - Crowd Wisdom
    if entry.agf:
        score += entry.agf * 2.0  # High weight on AGF
        
    # 4. Historical Performance (from DB)
    stats = history_stats.get(entry.horse_name)
    if stats:
        avg_rank = stats['avg_rank']
        count = stats['count']
        if count > 0:
            # Lower rank is better. 
            # Bonus for low average rank.
            # e.g. Avg Rank 1.0 -> +50 points
            # Avg Rank 10.0 -> +0 points
            rank_bonus = max(0, (15 - avg_rank) * 3)
            score += rank_bonus
            
    return score

def predict_izmir():
    db = next(get_db())
    today = date(2025, 12, 19)
    city = "İzmir"
    
    print(f"--- ANALYZING RACES FOR {city.upper()} ({today}) ---\n")
    
    # 1. Get Today's Races
    races = db.query(RaceModel).filter(
        RaceModel.date == today,
        RaceModel.city == city
    ).order_by(RaceModel.race_no).all()
    
    if not races:
        print("No races found for this date/city.")
        return

    # 2. Pre-fetch history stats for all horses
    # (Simple logic: average rank of horses in previous races)
    history_stats = {}
    
    # We need to find all horses in today's races first?
    # Or just query all history. 
    # Let's query per race to be efficient or simple loop.
    
    for race in races:
        print(f"\n🏁 RACE {race.race_no} | {race.distance_m}m {race.surface} |")
        
        candidates = []
        for entry in race.entries:
            # Fetch past average rank for this horse
            # Note: This is synchronous N+1, but fine for a script
            avg_rank = db.query(func.avg(EntryModel.rank)).filter(
                EntryModel.horse_name == entry.horse_name,
                EntryModel.rank != None
            ).scalar() or 10.0 # default mid-pack
            
            count = db.query(func.count(EntryModel.id)).filter(
                EntryModel.horse_name == entry.horse_name,
                EntryModel.rank != None
            ).scalar()
            
            stats = {'avg_rank': avg_rank, 'count': count}
            
            score = calculate_score(entry, {entry.horse_name: stats})
            candidates.append((entry, score, stats))
            
        # Sort by Score Descending
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        # Display Top 4
        print(f"   {'Horse':<20} | {'Jockey':<15} | {'HP':<3} | {'Form':<8} | {'Score':<5}")
        print("   " + "-"*70)
        for i, (e, score, stat) in enumerate(candidates[:4]):
            print(f" {i+1}. {e.horse_name:<20} | {e.jockey_name[:15]:<15} | {e.hp or '-':<3} | {e.form_score or '-':<8} | {score:.1f}")

if __name__ == "__main__":
    predict_izmir()
