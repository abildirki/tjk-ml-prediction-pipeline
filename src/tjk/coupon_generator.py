
import os
import sys
import datetime
import pandas as pd
import asyncio
from typing import List, Dict, Any

from tjk.storage.db import get_db
from tjk.storage.schema import RaceModel
from tjk.cli import scrape_range_async
from tjk.ml.inference import get_predictions_for_date

class CouponGenerator:
    def __init__(self):
        self.db = next(get_db())

    async def ensure_data(self, target_date: datetime.date, city: str):
        """Force scrape for target date. No caching for today."""
        print(f"🔄 CANLI SORGULAMA: {target_date} - {city}")
        # Always force scrape for today to avoid stale DB state
        await scrape_range_async(target_date, target_date)

    def process(self, city: str, target_date: datetime.date = None):
        """
        Generates coupons using the ML Pipeline.
        """
        if target_date is None:
            target_date = datetime.date.today()

        print(f"🚀 ML İşlem Başlatıldı: {city} - {target_date}")
        
        # 1. Scrape Data
        try:
            asyncio.run(self.ensure_data(target_date, city))
        except Exception as e:
            return {"error": f"Scraping Error: {str(e)}"}

        # 2. Get ML Predictions
        try:
            preds_df = get_predictions_for_date(target_date, city)
        except Exception as e:
            return {"error": f"Prediction Error: {str(e)}"}

        if preds_df is None or preds_df.empty:
            return {"error": f"⛔ {city} için ({target_date}) yarış verisi bulunamadı."}

        # 3. Generate Coupons logic (using ML probabilities)
        # Group by Race No
        races_dict = {}
        # Convert DF to list of dicts per race
        for race_no, group in preds_df.groupby('race_no'):
            # Sort by Win Probability
            runners = group.sort_values('prob_win', ascending=False).to_dict('records')
            races_dict[race_no] = runners
            
        race_nums = sorted(races_dict.keys())
        
        # Determine Sequences (6-Ganyan)
        sequences = []
        if set(range(1, 7)).issubset(race_nums):
            sequences.append({"name": "1. 6'lı Ganyan", "races": list(range(1, 7))})
        if set(range(4, 10)).issubset(race_nums):
            sequences.append({"name": "2. 6'lı Ganyan", "races": list(range(4, 10))})
            
        if not sequences:
            # Fallback: Just last 6 races if available
            if len(race_nums) >= 6:
                last_6 = race_nums[-6:]
                sequences.append({"name": "6'lı Ganyan", "races": last_6})
            else:
                 return {"error": f"⛔ 6 koşulu seri oluşturulamadı. Mevcut: {race_nums}"}

        combined_eco_txt = []
        combined_wide_txt = []
        combined_banko = []
        combined_risky = []
        
        header_lines = [
            f"📅 Tarih: {target_date}",
            f"🏙️ Şehir: {city}",
            f"🧠 Model: XGBoost (Win/Place/Surprise)",
            "-" * 30
        ]

        for seq in sequences:
            seq_name = seq['name']
            available_races = seq['races']
            
            eco_coupon = []
            wide_coupon = []
            banko_cand = None
            seq_risky = []
            
            for i, r_no in enumerate(available_races):
                leg = i + 1
                runners = races_dict[r_no]
                # Runners are already sorted by prob_win desc
                
                top1 = runners[0]
                N = len(runners)
                
                win_prob = top1['prob_win']
                gap = 0
                if N > 1:
                    gap = win_prob - runners[1]['prob_win']
                
                # Banko Condition: High Win Prob + Good Gap
                is_banko = (win_prob > 0.55) or (win_prob > 0.45 and gap > 0.25)
                
                if is_banko:
                    if banko_cand is None or win_prob > banko_cand['prob']:
                        banko_cand = {'name': top1['horse_name'], 'leg': leg, 'prob': win_prob}
                
                # Risk Condition
                if win_prob < 0.25:
                    seq_risky.append(f"Ayak {leg}")

                # --- STATIC COVERAGE LOGIC (Robust) ---
                # Eco: Top 4
                eco_sel = []
                if is_banko:
                    eco_sel = [top1['horse_name']]
                else:
                    take_n = min(4, N)
                    eco_sel = [r['horse_name'] for r in runners[:take_n]]
                     
                # Wide: Top 6 + Surprises
                wide_sel = []
                if is_banko:
                    wide_sel = [top1['horse_name']]
                else:
                    take_n_wide = min(6, N)
                    base_sel = [r['horse_name'] for r in runners[:take_n_wide]]

                    # Add Surprises (SP Prob > 40%)
                    surprises = [r['horse_name'] + "⚡" for r in runners if r.get('prob_sp', 0) > 0.4]
                    wide_sel = list(set(base_sel + surprises))

                eco_coupon.append(eco_sel)
                wide_coupon.append(wide_sel)

            # Apply Best Banko
            banko_msg = "Yok"
            if banko_cand:
                b_leg = banko_cand['leg']
                b_name = banko_cand['name']
                # Force Banko in both
                eco_coupon[b_leg-1] = [b_name + "⭐"]
                wide_coupon[b_leg-1] = [b_name + "⭐"]
                banko_msg = f"{b_name} (Ayak {b_leg}) - Güven: %{banko_cand['prob']*100:.0f}"
            
            # Format Text
            header = f"\n=== {seq_name} ==="
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
