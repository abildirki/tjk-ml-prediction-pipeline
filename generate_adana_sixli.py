import os
import sys
import datetime
import csv
import pandas as pd
from typing import List, Dict

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from tjk.storage.db import get_db
from tjk.storage.schema import RaceModel
from tjk.analysis.history_processor import HistoryProcessor
from tjk.analysis.decision_engine import DecisionEngine
from tjk.analysis.calibrator import ScoreCalibrator

# CONFIG
CITY_TARGET = "Adana"
OUTPUT_DIR = "outputs/predictions"
START_RACE = 4

# CONFIG
CITY_TARGET = "Adana"
OUTPUT_DIR = "outputs/predictions"
START_RACE = 4

def generate_coupons():
    # 1. HARD DATE BINDING
    target_date = datetime.date(2025, 12, 21)
    program_date = target_date
    score_date = target_date
    profile_snapshot_date = target_date
    
    print(f"Program Date: {program_date}")
    print(f"Score Date: {score_date}")
    print(f"Profile Snapshot Date: {profile_snapshot_date} (Data < {target_date})")
    print("Cache Used: NO (Fresh Buildup)")
    
    if target_date == datetime.date.today():
        print("ℹ️ Processing LIVE data for today.")
    
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        
    db = next(get_db())
    
    # 2. Build Memory (Strict Boundary)
    print(f"🧠 Hafıza oluşturuluyor (Bitiş: {profile_snapshot_date})...")
    processor = HistoryProcessor(db)
    # Using a safe start date for history. 2024-01-01 provides good context.
    processor.build_profiles(start_date=datetime.date(2024, 1, 1), end_date=profile_snapshot_date)
    
    # 3. Analyze
    print(f"📍 {CITY_TARGET} programı analiz ediliyor...")
    engine = DecisionEngine(db, processor.profiles)
    
    cities = [CITY_TARGET]
    raw_predictions = engine.analyze_daily_program(target_date, cities)
    
    if not raw_predictions:
        print(f"❌ {CITY_TARGET} yarış programı bulunamadı ({target_date}).")
        return

    # 4. Calibrate
    calibrator = ScoreCalibrator()
    calibrated = calibrator.calibrate(raw_predictions)
    
    # 4. Group by Race
    races_dict = {}
    for p in calibrated:
        r_no = p['race_no']
        if r_no not in races_dict: races_dict[r_no] = []
        races_dict[r_no].append(p)
        
    # Sequence: Start to Start+5
    sequence_nums = range(START_RACE, START_RACE + 6)
    
    # Check if races exist. If 9 is missing, use available.
    available_races = [r for r in sequence_nums if r in races_dict]
    
    if not available_races:
        print(f"❌ Belirtilen koşular ({START_RACE}-...) bulunamadı. Mevcut: {sorted(races_dict.keys())}")
        return

    print(f"🎫 6'LI GANYAN (RESMİ): {available_races[0]}-{available_races[-1]}")
    
    # --- PROGRAM GÜVENLİK KİLİDİ (VALIDATION) ---
    print("🔒 Program Güvenlik Kilidi Devrede...")
    
    # 1. Fetch Official DB Program for these races
    official_races = db.query(RaceModel).filter(
        RaceModel.date == target_date,
        RaceModel.city == CITY_TARGET,
        RaceModel.race_no.in_(available_races)
    ).all()
    
    # Map RaceNo -> [Official Horse Names]
    official_map = {}
    for r in official_races:
        entries = [e.horse_name for e in r.entries]
        official_map[r.race_no] = entries
        
    lines_summary = []
    lines_summary.append(f"ADANA 6'LI ({available_races[0]}-{available_races[-1]})")
    lines_summary.append(f"Tarih: {target_date} | Şehir: {CITY_TARGET}")
    lines_summary.append("-" * 40)
    lines_summary.append(f"{'Koşu':<5} | {'Program':<8} | {'Skorlanan':<8} | {'Durum':<10}")
    lines_summary.append("-" * 40)
    
    validation_failed = False
    
    valid_races_dict = {}
    
    for r_no in available_races:
        # DB entries
        db_horses = set(official_map.get(r_no, []))
        if not db_horses:
            print(f"❌ Koşu {r_no} için veritabanında kayıt bulunamadı!")
            validation_failed = True
            break
            
        # Prediction entries
        preds = races_dict.get(r_no, [])
        pred_horses = set(p['horse'] for p in preds)
        
        # 1. Filter predictions to ONLY include official horses
        valid_preds = [p for p in preds if p['horse'] in db_horses]
        valid_horses = set(p['horse'] for p in valid_preds)
        
        # 2. Check Coverage
        # Rule: If scored count < program count -> FAIL?
        # Note: Sometimes program has scratched horses not in predictions? 
        # But user rule: "skorlanan at sayısı < program at sayısı ise ... DUR"
        
        n_prog = len(db_horses)
        n_score = len(valid_horses)
        
        status = "✅ OK"
        if n_score < n_prog:
            # Check if likely scratched? DB usually doesn't delete scratch. 
            # If large mismatch, error.
            # If discrepancy is small (1-2), maybe scratch?
            # User rule is STRICT: "Eksik veri ... DUR".
            # We strictly enforce this for safety.
            status = "❌ EKSİK"
            validation_failed = True
        
        lines_summary.append(f"{r_no:<5} | {n_prog:<8} | {n_score:<8} | {status}")
        
        # Store validated predictions
        valid_races_dict[r_no] = valid_preds

    if validation_failed:
        print("\n".join(lines_summary))
        print("\n🚫 KRİTİK HATA: Program doğrulama başarısız. Kupon üretilmedi.")
        print("   (Skorlanan at sayısı programdan eksik veya veri uyuşmazlığı var.)")
        return

    print("✅ Program doğrulandı. Kupon üretiliyor...")
    lines_summary.append("-" * 40)
    
    eco_coupon = []
    wide_coupon = []
    
    debug_rows = []
    banko_candidate = None
    
    # Replace races_dict with valid_races_dict for subsequent steps
    races_dict = valid_races_dict
    
    # 5. Process Legs
    for i, r_no in enumerate(available_races):
        leg_idx = i + 1
        runners = races_dict[r_no]
        runners.sort(key=lambda x: x['race_pct'], reverse=True)
        
        N = len(runners)
        top1 = runners[0]
        pct = top1['race_pct']
        gap_pct = top1['race_gap_pct']
        
        top3_diff = 0
        if N >= 3:
            top3_diff = top1['race_pct'] - runners[2]['race_pct']
            
        # Risk Heuristic
        # (N>=12 ve gap_pct < 0.12) veya (top1 ile top3 ayrışması < 0.18) => riskli
        cond1 = (N >= 12 and gap_pct < 0.12)
        cond2 = (top3_diff < 0.18)
        is_risky = cond1 or cond2
        
        risk_icon = "🔥" if is_risky else "✅"
        
        # Banko Check
        # pct_top1 >= 0.985 AND gap >= thresh AND top3_diff >= 0.20
        gap_thresh = 0.05 + (0.8 / N) if N > 0 else 0
        is_strict_banko = False
        
        if pct >= 0.985 and gap_pct >= gap_thresh and top3_diff >= 0.20:
            is_strict_banko = True
            # Allow banko candidate if strictly met
            if banko_candidate is None: # Only one banko logic usually
                banko_candidate = {
                    'name': top1['horse'],
                    'leg': leg_idx,
                    'pct': pct, 
                    'gap': gap_pct,
                    'diff': top3_diff
                }
            elif pct > banko_candidate['pct']: # Pick stronger if multiple
                 banko_candidate = {
                    'name': top1['horse'],
                    'leg': leg_idx,
                    'pct': pct, 
                    'gap': gap_pct,
                    'diff': top3_diff
                }

        # Selection Counts
        # Eco: Normal=2, Risk=3
        # Wide: Normal=4, Risk=5
        n_eco = 3 if is_risky else 2
        n_wide = 5 if is_risky else 4
        
        eco_picked = [r['horse'] for r in runners[:n_eco]]
        wide_picked = [r['horse'] for r in runners[:n_wide]]
        
        # Surprise Logic
        # Label 'SÜRPRİZ ADAYI' if exists
        surprises = [r['horse'] for r in runners if r['calibrated_label'] == 'SÜRPRİZ ADAYI']
        # Also check simple surprise logic if label missing: pct > 0.60
        
        # Add to Wide only? Or just report to user?
        # User said: "Her ayakta varsa 1-2 “⚠️ sürpriz adayı”nı geniş kupon için ayrıca not düş"
        # Implies strictly listing them, maybe adding if fits?
        # I'll stick to listing them in output.
        
        # Also, make sure wide includes eco
        for h in eco_picked:
             if h not in wide_picked: wide_picked.append(h) # Should be covered by logic but safe
             
        # Store for Coupon
        eco_coupon.append(eco_picked)
        wide_coupon.append(wide_picked)
        
        # Debug Log
        for r in runners:
            tags = []
            if r['horse'] in eco_picked: tags.append("ECO")
            if r['horse'] in wide_picked: tags.append("WIDE")
            
            debug_rows.append({
                'race': r_no,
                'at_no': '-', # Not in model yet usually
                'at_adi': r['horse'],
                'score_raw': r['base_score'],
                'race_pct': r['race_pct'],
                'gap_pct': r['race_gap_pct'],
                'risk_flag': is_risky,
                'tags': "+".join(tags)
            })

        # Summary Line Construction
        surp_text = f" -> ⚠️ {', '.join(surprises[:2])}" if surprises else ""
        lines_summary.append(f"Ayak {leg_idx} (Koşu {r_no}) {risk_icon}")
        lines_summary.append(f"   Eko : {', '.join(eco_picked)}")
        lines_summary.append(f"   Geniş: {', '.join(wide_picked)} {surp_text}")
        lines_summary.append("")

    # Apply Banko
    if banko_candidate:
        b_leg = banko_candidate['leg']
        b_name = banko_candidate['name']
        print(f"\n🏆 BANKO SEÇİLDİ: {b_name} (Ayak {b_leg})")
        # Update Lists
        eco_coupon[b_leg-1] = [b_name]
        wide_coupon[b_leg-1] = [b_name]
        
        lines_summary.append(f"🏆 BANKO: {b_name} (Ayak {b_leg}) - (Pct: {banko_candidate['pct']:.2f}, Diff: {banko_candidate['diff']:.2f})")
    else:
        lines_summary.append("🚫 Bugün net banko yok.")

    # Write Output Files
    f_eco = f"{OUTPUT_DIR}/{target_date}_adana_sixli_start{START_RACE}_economic.txt"
    with open(f_eco, 'w', encoding='utf-8') as f:
        for i, legs in enumerate(eco_coupon):
            f.write(f"Ayak {i+1}: {','.join(legs)}\n")
            
    f_wide = f"{OUTPUT_DIR}/{target_date}_adana_sixli_start{START_RACE}_wide.txt"
    with open(f_wide, 'w', encoding='utf-8') as f:
        for i, legs in enumerate(wide_coupon):
            f.write(f"Ayak {i+1}: {','.join(legs)}\n")
            
    f_debug = f"{OUTPUT_DIR}/{target_date}_adana_sixli_start{START_RACE}_debug.csv"
    pd.DataFrame(debug_rows).to_csv(f_debug, index=False)
    
    # Print Final Summary
    print("\n" + "="*40)
    for l in lines_summary:
        print(l)
    print("="*40)
    print("✅ Tahmin başarıyla üretildi.")

if __name__ == "__main__":
    generate_coupons()
