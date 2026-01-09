import sys
import os
from datetime import date
from sqlalchemy import text, func, select
sys.path.append(os.path.join(os.getcwd(), "src"))

from tjk.storage.db import get_db
from tjk.storage.schema import RaceModel, EntryModel

# --- WEIGHTS ---
W_FORM = 25
W_TRACK = 20
W_JOCKEY = 15
W_WEIGHT = 15
W_PREP = 10
W_PACE = 15

def get_form_score(entry, db):
    """
    1. Form Durumu (%25)
    - Son 3-5 yarış performansı.
    - 1-3.lük puan, son yarış iyi derece ekstra.
    """
    raw_score = 0
    if not entry.form_score:
        return 0
    
    # "121112" -> read right to left (most recent often right in TJK strings? 
    # Actually usually left is most recent in some sources, but typically standard format is "654321".
    # User said "Son 3 yarış". Let's verify format later. Assuming Standard: Left=Oldest, Right=Newest.
    # Let's act on the last 3 chars.
    
    fs = str(entry.form_score).strip()
    if not fs: return 0
    
    last_3 = fs[-3:] # Get last 3 races
    
    # Points for recent 1st, 2nd, 3rd
    for i, char in enumerate(reversed(last_3)):
        # i=0 is most recent
        weight = 1.0 if i == 0 else 0.8 # Most recent worth more
        
        if char == '1': raw_score += 10 * weight
        elif char == '2': raw_score += 7 * weight
        elif char == '3': raw_score += 4 * weight
        elif char == '4': raw_score += 2 * weight
        
    # Max raw score approx 25-28. Normalize to 0-25 range.
    normalized = min(25, raw_score)
    return normalized

def get_track_dist_score(entry, race, db):
    """
    2. Pist + Mesafe (%20)
    - Aynı pist ve mesafedeki geçmişi.
    - Kum/Çim ayırımı. Mesafe +/- 200m tolerans.
    """
    # Find past races for this horse with similar conditions
    min_dist = race.distance_m - 200
    max_dist = race.distance_m + 200
    surface = race.surface # 'KUM'
    
    # Query DB for specific horse history
    # Join Entries -> Races
    history = db.execute(text("""
        SELECT e.rank 
        FROM entries e 
        JOIN races r ON e.race_id = r.race_id 
        WHERE e.horse_name = :hname 
          AND r.surface = :surf
          AND r.distance_m BETWEEN :dmin AND :dmax
          AND e.rank IS NOT NULL
          AND r.date < :rdate
        ORDER BY r.date DESC LIMIT 5
    """), {
        "hname": entry.horse_name,
        "surf": surface,
        "dmin": min_dist, 
        "dmax": max_dist,
        "rdate": race.date
    }).fetchall()
    
    if not history:
        # "İlk kez koşuyorsa -> düşük"
        return 5 # Base points for unknown
        
    points = 0
    count = 0
    for row in history:
        rank = row[0]
        if rank == 1: points += 10
        elif rank <= 3: points += 6
        elif rank <= 5: points += 3
        count += 1
        
    # Average performance? Or just "Has won before"?
    # "Aynı pist & mesafede kazandıysa -> yüksek"
    has_win = any(r[0] == 1 for r in history)
    
    final_score = 0
    if has_win: 
        final_score = 20 # Max score
    else:
        # Normalize based on average points
        avg_pts = points / count if count > 0 else 0
        # avg_pts max is 10 (all wins). 10 -> 20 score.
        final_score = avg_pts * 2
        
    return min(20, final_score)

def get_jockey_score(entry, db):
    """
    3. Jokey Etkisi (%15)
    - "Aynı jokeyle tekrar biniliyorsa -> Ciddi artı"
    - Jokeyin başarı oranı (Basit proxy: jockey table win %)
    """
    # 1. Check if same jockey rode last time
    last_race = db.execute(text("""
        SELECT e.jockey_name 
        FROM entries e 
        JOIN races r ON e.race_id = r.race_id 
        WHERE e.horse_name = :hname 
          AND r.date < :today
        ORDER BY r.date DESC LIMIT 1
    """), {"hname": entry.horse_name, "today": date.today()}).fetchone()
    
    same_jockey_bonus = 0
    if last_race and last_race[0] == entry.jockey_name:
        same_jockey_bonus = 5 # "Ciddi artı"
        
    # 2. Jockey Quality (General Win Rate proxy using this DB)
    # Count total wins / total races for this jockey
    stats = db.execute(text("""
        SELECT 
            COUNT(CASE WHEN rank = 1 THEN 1 END) as wins,
            COUNT(*) as total
        FROM entries 
        WHERE jockey_name = :jname
    """), {"jname": entry.jockey_name}).fetchone()
    
    win_rate = 0
    if stats[1] > 0:
        win_rate = stats[0] / stats[1] # e.g. 0.15 for 15%
        
    # Normalize win_rate (0.0 to 0.3 typically). Map 0.20+ to 10 pts.
    quality_score = min(10, win_rate * 50) 
    
    total = quality_score + same_jockey_bonus
    return min(15, total)

def get_weight_hp_score(entry, entries_in_race):
    """
    4. Kilo & Handikap (%15)
    - Rakiplere göre kilo avantajı.
    - Handikap puanı dengesi.
    """
    # Avg weight of race
    weights = [e.weight_kg for e in entries_in_race if e.weight_kg]
    if not weights: return 7.5
    avg_weight = sum(weights) / len(weights)
    
    # Avg HP
    hps = [e.hp for e in entries_in_race if e.hp]
    avg_hp = sum(hps) / len(hps) if hps else 50
    
    score = 0
    
    # Logic: Lower weight than avg is good.
    diff_kg = avg_weight - (entry.weight_kg or avg_weight)
    # diff > 0 means horse is lighter than avg (Good).
    # e.g. Avg 58, Horse 50 -> +8 kg diff.
    score += max(0, diff_kg * 1.0) # +8 pts for 8kg advantage? roughly.
    
    # Logic: Higher HP than avg is good (Class is higher).
    # e.g. HP 90 vs Avg 50 -> +40 diff.
    diff_hp = (entry.hp or 0) - avg_hp
    if diff_hp > 0:
        score += min(7, diff_hp * 0.2) # Max 7 pts from HP class diff
        
    return min(15, score + 5) # Base 5 pts

def get_prep_score(entry, db):
    """
    5. Antrenör + Hazırlık (%10)
    - Trainer success rate proxy (since no galop data).
    """
    # Trainer Stats
    if not entry.trainer_id: return 5
    
    stats = db.execute(text("""
        SELECT COUNT(*) FROM entries WHERE trainer_id = :tid AND rank = 1
    """), {"tid": entry.trainer_id}).scalar() or 0
    
    # Simple volume proxy: More wins = Better Prep System?
    # Cap at 10.
    return min(10, stats * 0.5)

def get_pace_score(entry):
    """
    6. Senaryo (%15)
    - Hard to calculate without run style data.
    - Placeholder: 7.5 (Neutral).
    """
    return 7.5

def analyze_race_advanced(target_date, city):
    db = next(get_db())
    print(f"\n🚀 ADVANCED ANALYSIS FOR {city.upper()} ({target_date})\n")
    print(f"Formula: Form(25) + Track(20) + Jockey(15) + Weight(15) + Prep(10) + Pace(15) = 100\n")

    races = db.query(RaceModel).filter(
        RaceModel.date == target_date,
        RaceModel.city == city
    ).order_by(RaceModel.race_no).all()
    
    if not races:
        print("No races found.")
        return

    all_results = []
    for race in races:
        # print(f"🔸 RACE {race.race_no} | {race.distance_m}m {race.surface}")
        
        candidates = []
        entries_list = [e for e in race.entries] # materialize
        
        for entry in entries_list:
            s_form = get_form_score(entry, db)
            s_track = get_track_dist_score(entry, race, db)
            s_jockey = get_jockey_score(entry, db)
            s_weight = get_weight_hp_score(entry, entries_list)
            s_prep = get_prep_score(entry, db)
            s_pace = get_pace_score(entry)
            
            total = s_form + s_track + s_jockey + s_weight + s_prep + s_pace
            
            candidates.append({
                'name': entry.horse_name,
                'total': total,
                'breakdown': [s_form, s_track, s_jockey, s_weight, s_prep, s_pace],
                'race_no': race.race_no,
                'city': race.city
            })
            
        candidates.sort(key=lambda x: x['total'], reverse=True)
        all_results.extend(candidates)
        
        # Keep printing for backward compatibility or logging
        # print(f"   {'Horse':<18} | {'Tot':<5} | {'Frm':<4} {'Trk':<4} {'Joc':<4} {'Wgt':<4} {'Prp':<4} {'Pce':<4}")
        # print("   " + "-"*60)
        # for c in candidates[:4]:
        #    pass 

    return all_results

if __name__ == "__main__":
    analyze_race_advanced(date(2025, 12, 19), "İzmir")
