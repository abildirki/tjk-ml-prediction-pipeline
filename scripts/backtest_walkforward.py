import os
import sys
import datetime
import csv
import pandas as pd
from typing import List, Dict
from sqlalchemy import func

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from tjk.storage.db import get_db
from tjk.storage.schema import RaceModel, EntryModel
from tjk.analysis.history_processor import HistoryProcessor
from tjk.analysis.decision_engine import DecisionEngine
from tjk.analysis.calibrator import ScoreCalibrator

# CONFIG
START_DATE = datetime.date(2025, 5, 5)
END_DATE = datetime.date.today()
OUTPUT_DIR = "outputs/backtest"
DAILY_CSV = f"{OUTPUT_DIR}/daily_results.csv"
SUMMARY_FILE = f"{OUTPUT_DIR}/summary_report.txt"

def ensure_dirs():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

def get_actual_result(db, city, race_no):
    """
    Get the winner (rank=1) for a specific race.
    Returns (horse_name, rank)
    Actually returns a dict of horse->rank for checking all preds.
    """
    entries = db.query(EntryModel).join(RaceModel).filter(
        RaceModel.city == city,
        RaceModel.race_no == race_no,
        RaceModel.date == db_search_date # This requires careful handling inside the loop
    ).all()
    # Wait, simple way: 
    # Pass race_id or filter by date+city+race_no
    pass

def run_backtest():
    ensure_dirs()
    db = next(get_db())
    
    print(f"🚀 STARTING WALK-FORWARD BACKTEST")
    print(f"📅 Range: {START_DATE} -> {END_DATE}")
    
    # 1. Warm-up History
    # We need to build profiles using data BEFORE the start date.
    # Assuming valid data starts reasonable early, let's use 2024-01-01 as hard start.
    history_start = datetime.date(2024, 1, 1)
    
    processor = HistoryProcessor(db)
    print(f"⏳ Warming up profiles (History < {START_DATE})...")
    processor.build_profiles(start_date=history_start, end_date=START_DATE)
    
    engine = DecisionEngine(db, processor.profiles)
    calibrator = ScoreCalibrator()
    
    # Prepare Result Log
    results_log = []
    
    # Iterate Days
    current_date = START_DATE
    total_days = (END_DATE - START_DATE).days + 1
    
    # Open CSV for streaming writes
    with open(DAILY_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        header = [
            'Date', 'City', 'Race', 'Banko_Horse', 'Banko_Rank', 'Banko_Win', 'Banko_Top3',
            'Is_Scientific_Winner_In_Eco', 'Is_Scientific_Winner_In_Wide', 
            'Surprise_Candidate', 'Surprise_Rank', 'Surprise_Win', 'Surprise_Place'
        ]
        writer.writerow(header)
        
        step = 0
        while current_date <= END_DATE:
            step += 1
            print(f"\n🔄 [{step}/{total_days}] Processing {current_date}...")
            
            # 1. Identify Races
            races_query = db.query(RaceModel).filter(RaceModel.date == current_date).all()
            if not races_query:
                print(f"   ⚠️ No races found for {current_date}")
                current_date += datetime.timedelta(days=1)
                continue
                
            cities = list(set(r.city for r in races_query))
            print(f"   📍 Cities: {cities}")
            
            # 2. Predict (Using profiles UP TO yesterday)
            # DecisionEngine uses self.profiles (which are currently up to yesterday)
            raw_preds = engine.analyze_daily_program(current_date, cities)
            
            if not raw_preds:
                print("   ⚠️ No predictions generated.")
                current_date += datetime.timedelta(days=1)
                continue
                
            # 3. Calibrate
            calibrated = calibrator.calibrate(raw_preds)
            
            # 4. Evaluate Results
            # Prepare map of Actual Results for this day
            # (City, RaceNo) -> {HorseName: Rank}
            actuals = {}
            for r in races_query:
                race_map = {}
                for e in r.entries:
                    if e.rank:
                        race_map[e.horse_name] = e.rank
                actuals[(r.city, r.race_no)] = race_map
            
            # Group predictions by Race
            race_groups = {}
            for p in calibrated:
                key = (p['city'], p['race_no'])
                if key not in race_groups: race_groups[key] = []
                race_groups[key].append(p)
                
            day_rows = []
            
            for (city, r_no), runners in race_groups.items():
                race_actuals = actuals.get((city, r_no), {})
                if not race_actuals:
                    continue # No results to check (maybe cancelled or future?)
                    
                # Find Banko
                banko_runner = next((r for r in runners if r['calibrated_label'] == 'BANKO'), None)
                
                # Check Banko
                b_name = banko_runner['horse'] if banko_runner else None
                b_rank = race_actuals.get(b_name) if b_name else None
                b_win = 1 if (b_rank == 1) else 0
                b_top3 = 1 if (b_rank and b_rank <= 3) else 0
                
                # Check Coupon Coverage
                # Eco Set
                eco_horses = {r['horse'] for r in runners if 'EKO' in r.get('coupon_tags', '')}
                wide_horses = {r['horse'] for r in runners if 'GENIS' in r.get('coupon_tags', '')}
                
                # Winner
                winner_name = next((h for h, r in race_actuals.items() if r == 1), None)
                
                is_in_eco = 1 if (winner_name and winner_name in eco_horses) else 0
                is_in_wide = 1 if (winner_name and winner_name in wide_horses) else 0
                
                # Check Surprise
                surprises = [r for r in runners if r['calibrated_label'] == 'SÜRPRİZ ADAYI']
                
                # For CSV, if multiple surprises, create multiple rows or just log first?
                # Let's log 'Surprise Hit' if ANY surprise won/placed
                surp_name = None
                surp_rank = None
                surp_win = 0
                surp_place = 0
                
                if surprises:
                    # Pick the best performing surprise or just list the first?
                    # Let's verify if ANY surprise did well
                    for s in surprises:
                        sr = race_actuals.get(s['horse'])
                        if sr:
                            if sr == 1: 
                                surp_win = 1
                                surp_name = s['horse']
                                surp_rank = sr
                                break # Found a winner!
                            if sr <= 3:
                                surp_place = 1
                                surp_name = s['horse'] # Keep looking for winner though? 
                                surp_rank = sr
                                
                    if not surp_name and surprises:
                         # No hit, just log the first one as failing
                         surp_name = surprises[0]['horse']
                         surp_rank = race_actuals.get(surp_name)

                # Write Row
                row = [
                    current_date, city, r_no,
                    b_name, b_rank, b_win, b_top3,
                    is_in_eco, is_in_wide,
                    surp_name, surp_rank, surp_win, surp_place
                ]
                writer.writerow(row)
                f.flush()
                results_log.append(row)
            
            # 5. Update Profiles (Learning Step)
            # Ingest today's results so they become "History" for tomorrow
            # print("   🧠 Learning from today's results...")
            processor.ingest_daily_races(current_date)
            
            current_date += datetime.timedelta(days=1)
            
    # generate Summary
    # Call the external analysis script logic if available, or use inline
    try:
        from analyze_backtest import analyze
        print("\n📊 Running Post-Analysis...")
        analyze()
    except ImportError:
        print("⚠️ analyze_backtest module not found. Using legacy summary.")
        generate_summary(results_log)
    
    print("✅ Backtest Complete.")

def generate_summary(rows):
    # Backward compatibility wrapper if analyze_backtest is missing
    # ... (same as before but simplified or kept as fallback)
    if not rows:
        print("No results to summarize.")
        return

    df = pd.DataFrame(rows, columns=[
        'Date', 'City', 'Race', 'Banko_Horse', 'Banko_Rank', 'Banko_Win', 'Banko_Top3',
        'Eco_Has_Winner_In_Leg', 'Wide_Has_Winner_In_Leg', 
        'Surprise_Candidate', 'Surprise_Rank', 'Surprise_Win', 'Surprise_Place'
    ])
    
    # ... (Simple fallback summary logic)

if __name__ == "__main__":
    run_backtest()
