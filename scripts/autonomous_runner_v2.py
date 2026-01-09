
import os
import sys
import datetime
import logging
import csv
from typing import List

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from tjk.storage.db import get_db
from tjk.storage.schema import RaceModel
from tjk.analysis.history_processor import HistoryProcessor
from tjk.analysis.decision_engine import DecisionEngine
from tjk.analysis.calibrator import ScoreCalibrator

def setup_logging(date_str):
    if not os.path.exists("outputs/logs"):
        os.makedirs("outputs/logs")
        
    log_file = f"outputs/logs/autonomous_{date_str}.log"
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger("AutonomousEngine")

def resolve_analysis_date(logger):
    # 1. Test Mode: Explicit --date argument
    if len(sys.argv) > 1:
        date_str = sys.argv[1]
        try:
            target_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
            logger.info(f"🔧 Test Mode detected. Forced Date: {target_date}")
            return target_date
        except ValueError:
            logger.error("Invalid date format. Use YYYY-MM-DD")
            sys.exit(1)

    # 2. Autonomous Mode: Smart Fallback (Today -> Yesterday)
    today = datetime.date.today()
    csv_today = f"data/daily/{today}.csv"
    
    if os.path.exists(csv_today):
        logger.info(f"📅 Daily Data found for TODAY: {today}")
        return today
        
    yesterday = today - datetime.timedelta(days=1)
    csv_yesterday = f"data/daily/{yesterday}.csv"
    
    if os.path.exists(csv_yesterday):
        logger.warning(f"⚠️ Data for TODAY ({today}) not found. Falling back to YESTERDAY ({yesterday}).")
        return yesterday
        
    logger.error(f"❌ No data found for Today ({today}) OR Yesterday ({yesterday}). Stopping.")
    sys.exit(0) # Safe stop, not a crash

def main():
    # Setup temp logger for date resolution (before final log file is set)
    logging.basicConfig(level=logging.INFO)
    temp_logger = logging.getLogger("Init")
    
    target_date = resolve_analysis_date(temp_logger)
    date_str = str(target_date)
    
    # Re-setup logging for the specific date
    logger = setup_logging(date_str)
    logger.info(f"🚀 Starting Autonomous Profile Engine for {date_str}")
    
    # 1. Pipeline Check
    csv_path = f"data/daily/{date_str}.csv"
    if not os.path.exists(csv_path):
        logger.warning(f"CSV file not found: {csv_path}. Proceeding with DB check...")
        
    db = next(get_db())
    
    # 2. Build Profiles (The "Memory")
    logger.info("🧠 Replaying history to build horse profiles...")
    processor = HistoryProcessor(db)
    # Start usually from 2025-05-05 per instruction
    profiles = processor.build_profiles(start_date=datetime.date(2025, 5, 5))
    logger.info(f"✅ Memory built. Tracking {len(profiles)} horses.")
    
    # 3. Analyze Today
    logger.info("🔮 Running Decision Engine for today's races...")
    engine = DecisionEngine(db, profiles)
    
    # Get active cities
    races = db.query(RaceModel.city).filter(RaceModel.date == target_date).distinct().all()
    cities = [r[0] for r in races]
    
    if not cities:
        logger.error(f"No races found for {target_date} in DB.")
        sys.exit(1)
        
    logger.info(f"Target Cities: {cities}")
    raw_predictions = engine.analyze_daily_program(target_date, cities)
    
    # 4. Calibration
    logger.info("⚖️ Running Calibration Engine...")
    calibrator = ScoreCalibrator()
    calibrated_predictions = calibrator.calibrate(raw_predictions)
    
    # 5. Save Output
    output_dir = "outputs/predictions"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    output_csv = f"{output_dir}/{date_str}_profile_calibrated.csv"
    logger.info(f"Saving calibrated predictions to {output_csv}...")
    
    try:
        with open(output_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['City', 'Race', 'Horse', 'RawScore', 'Pct', 'Gap', 'Label', 'Coupon', 'Stats'])
            
            for p in calibrated_predictions:
                writer.writerow([
                    p['city'], p['race_no'], p['horse'], 
                    p['base_score'], p['race_pct'], p['race_gap_pct'], 
                    p['calibrated_label'], p['coupon_tags'], p['profile_stats']
                ])
    except Exception as e:
        logger.error(f"Failed to save CSV: {e}")
        
    # 6. Summary
    print_summary(calibrated_predictions, logger)
    logger.info("✅ Autonomous Cycle Completed.")

def print_summary(predictions: List[dict], logger):
    print("\n" + "="*60)
    print("🤖 OTONOM PROFİL MOTORU ANALİZ RAPORU (KALİBRE EDİLMİŞ)")
    print("="*60)
    
    # Group by City > Race
    races = {}
    for p in predictions:
        key = (p['city'], p['race_no'])
        if key not in races: races[key] = []
        races[key].append(p)
        
    for (city, race_no), runners in races.items():
        print(f"\n📍 {city} {race_no}. Koşu")
        print("-" * 40)
        
        # Sort by Pct (Rank)
        runners.sort(key=lambda x: x['race_pct'], reverse=True)
        
        # Display Top Runners
        for r in runners[:4]:
            label = r['calibrated_label']
            tags = r['coupon_tags']
            marker = "  "
            if label == "BANKO": marker = "🏆 "
            elif label == "GÜÇLÜ FAVORİ": marker = "✨ "
            elif label == "SÜRPRİZ ADAYI": marker = "⚠️ "
            
            print(f" {marker}{r['horse']:<15} (Pct: {r['race_pct']:.2f} | Gap: {r['race_gap_pct']:.2f} | {label}) [{tags}]")
                
    print("\n" + "="*60)

if __name__ == "__main__":
    main()
