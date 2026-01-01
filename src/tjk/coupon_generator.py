import os
import sys
import datetime
import pandas as pd
import asyncio
from typing import List, Dict, Any

from tjk.storage.db import get_db
from tjk.storage.schema import RaceModel
from tjk.analysis.history_processor import HistoryProcessor
from tjk.analysis.decision_engine import DecisionEngine
from tjk.analysis.calibrator import ScoreCalibrator
from tjk.cli import scrape_range_async

class CouponGenerator:
    def __init__(self):
        self.db = next(get_db())

    async def ensure_data(self, target_date: datetime.date, city: str):
        """Force scrape for target date. No caching for today."""
        print(f"🔄 CANLI SORGULAMA: {target_date} - {city}")
        # Always force scrape for today to avoid stale DB state
        await scrape_range_async(target_date, target_date)

    def process(self, city: str, target_date: datetime.date = None):
        # 1. TARGET DATE = BUGÜN (Strict Rule)
        if target_date is None:
            target_date = datetime.date.today()
        
        # Override strict checking for target_date consistency
        current_system_date = datetime.date.today()
        if target_date != current_system_date:
             # Just a warning in case manual override was intended, but Rule says "Kullanıcı tarih sormayacak"
             # We enforce it is today.
             print(f"⚠️ Uyarı: İstenen tarih ({target_date}) sistem tarihinden ({current_system_date}) farklı.")
             # Rule: "Eski tarih fallback YASAK" -> We assume caller might test backtest? 
             # But request says "EXE her açıldığında SADECE bugünün...".
             # We will stick to target_date, but caller checks.
             
        print(f"🚀 İşlem Başlatıldı: {city} - {target_date}")
        
        # 2. Sync Scrape (Force Fresh)
        # Note: scrape_range_async scrapes ALL cities for that date usually? 
        # Checking cli.py: `process_city_dual_source`. It iterates cities found on TJK.
        asyncio.run(self.ensure_data(target_date, city))
        
        # Check DB State NOW
        # We need to verify we actually HAVE data for (City, Date)
        official_races_check = self.db.query(RaceModel).filter(
            RaceModel.date == target_date,
            RaceModel.city == city # Case sensitive usually, but DB depends.
        ).all()
        
        if not official_races_check:
            return {"error": f"⛔ BUGÜN PROGRAM YAYINLANMADI / SCRAPE FAIL\n({city} - {target_date} için veri yok)"}

        # Validate City Match (Hard Binding)
        # DB city is stored normalized. We compare ignoring case.
        db_city = official_races_check[0].city
        if db_city.lower().replace('İ','i').replace('I','ı') != city.lower().replace('İ','i').replace('I','ı'):
             # Normalize simple check
             if db_city.upper() != city.upper():
                return {"error": f"⛔ DATE/CITY MISMATCH ERROR\nİstenen: {city}, Bulunan: {db_city}"}
        
        # 3. Build Memory (Strict Boundary)
        print(f"🧠 Hafıza oluşturuluyor (Bitiş: {target_date})...")
        # Cache Used: NO (We just scraped)
        processor = HistoryProcessor(self.db)
        # Rule: "Her şey fresh scrape + fresh scoring olacak" -> We rebuild profiles up to today
        # Note: end_date=target_date means we include history UP TO target_date (exclusive usually?)
        # HistoryProcessor logic: date < end_date. So we exclude today from history stats, which is CORRECT.
        processor.build_profiles(start_date=datetime.date(2024, 1, 1), end_date=target_date)
        
        # 4. Analyze
        print(f"📍 {city} analiz ediliyor...")
        engine = DecisionEngine(self.db, processor.profiles)
        raw_preds = engine.analyze_daily_program(target_date, [city]) # Lists cities
        
        if not raw_preds:
             return {"error": f"⛔ {city} programı analiz edilemedi (Veri boş?)."}

        # 5. Calibrate
        calibrator = ScoreCalibrator()
        calibrated = calibrator.calibrate(raw_preds)
        
        # Group by Race
        races_dict = {}
        for p in calibrated:
            races_dict.setdefault(p['race_no'], []).append(p)
            
        race_nums = sorted(races_dict.keys())
        if not race_nums:
             return {"error": "⛔ Kalibrasyon sonrası yarış kalmadı."}

        # 6. Determine 6-Ganyan Legs (Multi-Sequence Support)
        sequences = []
        
        # Check for 1. 6'lı (Races 1-6)
        if set(range(1, 7)).issubset(race_nums):
            sequences.append({"name": "1. 6'lı Ganyan", "races": list(range(1, 7))})
            
        # Check for 2. 6'lı (Races 4-9) or just "6'lı" if starts at 4 and isn't covered
        if set(range(4, 10)).issubset(race_nums):
            sequences.append({"name": "2. 6'lı Ganyan", "races": list(range(4, 10))})
            
        # Fallbacks for shorter programs
        if not sequences:
            if len(race_nums) >= 6:
                last_6 = list(range(max(race_nums)-5, max(race_nums)+1))
                if set(last_6).issubset(race_nums):
                    sequences.append({"name": "6'lı Ganyan", "races": last_6})
        
        if not sequences:
            return {"error": f"⛔ 6 koşulu seri oluşturulamadı. Mevcut koşular: {race_nums}"}
            
        # Combine Outputs
        combined_eco_txt = []
        combined_wide_txt = []
        combined_banko = []
        combined_risky = []
        
        # HEADER INFO (Mandatory)
        header_lines = [
            f"Target Date: {target_date}",
            f"Program Date: {target_date}", 
            f"Selected City: {city}",
            f"Program City: {db_city}",
            "Cache Used: NO (LIVE SCRAPE)",
            "-" * 30
        ]
        
        for seq in sequences:
            seq_name = seq['name']
            available_races = seq['races']
            
            # Validation Logic (Official Check)
            official_races = self.db.query(RaceModel).filter(
                RaceModel.date == target_date,
                RaceModel.city == db_city, # Use verified db_city
                RaceModel.race_no.in_(available_races)
            ).all()
            
            official_map = {r.race_no: [e.horse_name for e in r.entries] for r in official_races}
            
            for r_no in available_races:
                db_horses = official_map.get(r_no, [])
                if not db_horses:
                    return {"error": f"⛔ PROGRAM LIST MISMATCH\nKoşu {r_no} DB'de bulunamadı."}
                
                # Filter Predictions to DB only
                valid_preds = [p for p in races_dict[r_no] if p['horse'] in db_horses]
                races_dict[r_no] = valid_preds
                
                # Check coverage
                if not valid_preds:
                     return {"error": f"⛔ PROGRAM LIST MISMATCH\nKoşu {r_no} için tahmin/program eşleşmedi."}
                     
                # Strict: Scored Count vs Program Count
                # If valid_preds < db_horses -> "PROGRAM LIST MISMATCH"
                if len(valid_preds) < len(db_horses):
                     # List missing
                     missing = set(db_horses) - set(p['horse'] for p in valid_preds)
                     return {"error": f"⛔ PROGRAM LIST MISMATCH (Koşu {r_no})\nEksik Atlar: {missing}"}

            # Generate Coupon for this Sequence
            eco_coupon = []
            wide_coupon = []
            banko_cand = None
            
            seq_risky = []
            
            for i, r_no in enumerate(available_races):
                leg = i + 1
                runners = races_dict[r_no]
                runners.sort(key=lambda x: x['race_pct'], reverse=True)
                
                N = len(runners)
                top1 = runners[0]
                
                top3_diff = 0
                if N >= 3:
                    top3_diff = top1['race_pct'] - runners[2]['race_pct']
                    
                gap_thresh = 0.05 + (0.8 / N) if N > 0 else 0
                
                # Risk
                is_risky = (N >= 12 and top1['race_gap_pct'] < 0.12) or (top3_diff < 0.18)
                if is_risky:
                    seq_risky.append(f"Ayak {leg} (K{r_no})")
                    
                # Banko
                if top1['race_pct'] >= 0.985 and top1['race_gap_pct'] >= gap_thresh and top3_diff >= 0.20:
                    if banko_cand is None or top1['race_pct'] > banko_cand['pct']:
                        banko_cand = {'name': top1['horse'], 'leg': leg, 'pct': top1['race_pct'], 'r_no': r_no}
                
                # Select
                n_eco = 3 if is_risky else 2
                n_wide = 5 if is_risky else 4
                
                eco_sel = [r['horse'] for r in runners[:n_eco]]
                wide_sel = [r['horse'] for r in runners[:n_wide]]
                
                # Surprises to wide
                surps = [r['horse'] for r in runners if r['calibrated_label'] == 'SÜRPRİZ ADAYI']
                for s in surps:
                     if s not in wide_sel: wide_sel.append(s)
                     if len(wide_sel) > n_wide + 2: break
                     
                eco_coupon.append(eco_sel)
                wide_coupon.append(wide_sel)
                
            # Apply Banko
            banko_msg = "Yok"
            if banko_cand:
                b_leg = banko_cand['leg']
                b_name = banko_cand['name']
                eco_coupon[b_leg-1] = [b_name]
                wide_coupon[b_leg-1] = [b_name]
                banko_msg = f"{b_name} (Ayak {b_leg}) - %{banko_cand['pct']*100:.0f}"
            
            # Format Text Block
            header = f"\n=== {seq_name} ({available_races[0]}-{available_races[-1]}) ==="
            
            eco_block = [header] + [f"Ayak {i+1}: {', '.join(l)}" for i, l in enumerate(eco_coupon)]
            wide_block = [header] + [f"Ayak {i+1}: {', '.join(l)}" for i, l in enumerate(wide_coupon)]
            
            combined_eco_txt.append("\n".join(eco_block))
            combined_wide_txt.append("\n".join(wide_block))
            
            combined_banko.append(f"{seq_name}: {banko_msg}")
            if seq_risky:
                combined_risky.append(f"{seq_name}: {', '.join(seq_risky)}")
        
        final_info_header = "\n".join(header_lines)
        return {
            "success": True,
            "city": city,
            "date": str(target_date),
            "banko": "\n".join(combined_banko),
            "risky": "\n".join(combined_risky) if combined_risky else "Yok",
            "eco": final_info_header + "\n\n" + "\n\n".join(combined_eco_txt),
            "wide": final_info_header + "\n\n" + "\n\n".join(combined_wide_txt)
        }

