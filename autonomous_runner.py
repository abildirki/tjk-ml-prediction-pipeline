
import os
import sys
import datetime
import logging
import csv
from sqlalchemy import text

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from tjk.storage.db import get_db
from tjk.storage.schema import RaceModel
import predict_advanced

def setup_logging(date_str):
    log_file = f"outputs/logs/{date_str}.log"
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger()

def main():
    today = datetime.date.today()
    date_str = str(today)
    
    logger = setup_logging(date_str)
    logger.info(f"Starting Autonomous Analysis for {date_str}")
    
    # 1. Check CSV existence
    csv_path = f"data/daily/{date_str}.csv"
    if not os.path.exists(csv_path):
        logger.error("DATA_NOT_FOUND: CSV file not found in data/daily/")
        print("DATA_NOT_FOUND") # Explicitly print as per requirement implication
        sys.exit(1)
        
    logger.info("CSV found. Starting Analysis Pipeline...")
    
    # 2. Pipeline: Feature Engineering & Prediction (Powered by predict_advanced)
    db = next(get_db())
    
    # Find active cities for today
    races = db.query(RaceModel.city).filter(RaceModel.date == today).distinct().all()
    cities = [r[0] for r in races]
    
    if not cities:
        logger.warning("No races found in DB for today, even though CSV exists. (Sync issue?)")
        sys.exit(0)
    
    logger.info(f"Target Cities: {cities}")
    
    all_predictions = []
    
    for city in cities:
        logger.info(f"Analyzing {city}...")
        results = predict_advanced.analyze_race_advanced(today, city)
        if results:
            all_predictions.extend(results)
            
    # 3. Save Results
    output_csv = f"outputs/predictions/{date_str}_results.csv"
    logger.info(f"Saving results to {output_csv}...")
    
    try:
        with open(output_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['City', 'Race', 'Horse', 'TotalScore', 'Label', 'Form', 'Track', 'Jockey', 'Weight', 'Prep', 'Pace'])
            
            for p in all_predictions:
                score = p['total']
                label = "SURPRIZ"
                if score >= 85: label = "BANKO"
                elif score >= 75: label = "FAVORİ"
                elif score >= 65: label = "KUPON"
                
                b = p['breakdown']
                writer.writerow([
                    p['city'], 
                    p['race_no'], 
                    p['name'], 
                    f"{score:.1f}", 
                    label,
                    f"{b[0]:.0f}", f"{b[1]:.0f}", f"{b[2]:.0f}", f"{b[3]:.0f}", f"{b[4]:.0f}", f"{b[5]:.0f}"
                ])
    except Exception as e:
        logger.error(f"Failed to save CSV: {e}")
        sys.exit(1)
        
    # 4. Summary Output
    logger.info("Generating Summary Report...")
    
    bankoes = [p for p in all_predictions if p['total'] >= 85]
    favorites = [p for p in all_predictions if 75 <= p['total'] < 85]
    
    # Sort bankoes by score desc
    bankoes.sort(key=lambda x: x['total'], reverse=True)
    
    print("\n" + "="*40)
    print(f"ANALİZ ÖZETİ ({date_str})")
    print("="*40)
    
    if bankoes:
        print("\n🏆 GÜNÜN BANKOLARI:")
        for b in bankoes:
            print(f"  • {b['city']} {b['race_no']}. Koşu: {b['name']} (Puan: {b['total']:.1f})")
    else:
        print("\n⚠️ Bugün net banko bulunamadı.")
        
    if favorites:
        print("\n✨ GÜÇLÜ FAVORİLER:")
        for f in favorites[:5]: # Top 5
             print(f"  • {f['city']} {f['race_no']}. Koşu: {f['name']} (Puan: {f['total']:.1f})")
             
    print("\n✅ Analiz tamamlandı. Detaylar:")
    print(f"   - {output_csv}")
    print(f"   - {log_file}")
    print("="*40 + "\n")

if __name__ == "__main__":
    main()
