import pandas as pd
import numpy as np
import os
import json
import logging
from datetime import timedelta, date
from typing import List, Optional

from tjk.features.builder import build_features_for_dataset
from tjk.ml.train import (
    train_place_model, train_win_model, train_sp_model, 
    predict_with_model, FEATURE_COLS
)
from tjk.decision.weighting import calculate_dynamic_score
from tjk.decision.risk import classify_race_risk

# Ensure log dir exists
os.makedirs("outputs/sim", exist_ok=True)

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("outputs/sim/simulation.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("TJKSimulator")

class DailySimulator:
    def __init__(self, start_date: str, end_date: str, train_window: str = "all", resume: bool = False):
        self.start_date = pd.to_datetime(start_date).date()
        self.end_date = pd.to_datetime(end_date).date()
        self.train_window = train_window # 'all' or int (days)
        self.resume = resume
        
        self.output_dir = "outputs/sim"
        self.daily_dir = f"{self.output_dir}/daily"
        os.makedirs(self.daily_dir, exist_ok=True)
        
        self.state_file = f"{self.output_dir}/state.json"
        
        # Load Data ONCE (InMemory optimization, but filter carefully)
        logger.info("Loading full dataset...")
        self.full_df = build_features_for_dataset()
        self.full_df['date'] = pd.to_datetime(self.full_df['date'])
        logger.info(f"Loaded {len(self.full_df)} rows.")

    def get_state(self):
        if self.resume and os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load state: {e}")
        return {"last_completed_date": None}

    def save_state(self, date_str):
        with open(self.state_file, 'w') as f:
            json.dump({"last_completed_date": date_str}, f)

    def run(self):
        state = self.get_state()
        last_date = state.get("last_completed_date")
        
        current_date = self.start_date
        
        # Loop
        while current_date <= self.end_date:
            date_str = current_date.isoformat()
            
            # Resume Check
            if last_date and current_date <= pd.to_datetime(last_date).date():
                logger.info(f"Skipping {date_str} (Already done).")
                current_date += timedelta(days=1)
                continue
                
            try:
                self.process_day(current_date)
                self.save_state(date_str)
            except Exception as e:
                logger.error(f"CRITICAL ERROR on {date_str}: {e}", exc_info=True)
                with open(f"{self.output_dir}/errors.csv", "a") as f:
                    f.write(f"{date_str},{str(e)}\n")
                # Continue? Yes, for stability test.
            
            current_date += timedelta(days=1)
            
        logger.info("Simulation Complete.")

    def process_day(self, sim_date):
        logger.info(f"simulate_day: {sim_date}")
        ts = pd.to_datetime(sim_date)
        
        # 1. Strict Filter
        # Train: < sim_date
        # Test: == sim_date
        if self.train_window == "all":
            train_mask = self.full_df['date'] < ts
        else:
            try:
                window_days = int(self.train_window)
                start_window = ts - timedelta(days=window_days)
                train_mask = (self.full_df['date'] < ts) & (self.full_df['date'] >= start_window)
            except:
                train_mask = self.full_df['date'] < ts # Fallback
                
        test_mask = self.full_df['date'] == ts
        
        train_df = self.full_df[train_mask]
        test_df = self.full_df[test_mask]
        
        if len(test_df) == 0:
            logger.warning(f"No races found for {sim_date}. Skipping.")
            return

        if len(train_df) < 100:
            logger.warning(f"Not enough history for {sim_date} ({len(train_df)} rows). Skipping.")
            return

        logger.info(f"Training on {len(train_df)} rows. Predicting {len(test_df)} rows.")

        # 2. Train Models (Win, Place, SP)
        model_win = train_win_model(train_df)
        model_place = train_place_model(train_df)
        model_sp = train_sp_model(train_df)
        
        # 3. Predict via Predictor
        # Note: We use existing logic manually to ensure no leaks
        # We need raw features in test_df
        
        # Predict Probabilities
        prob_win = predict_with_model(model_win, test_df)
        prob_place = predict_with_model(model_place, test_df)
        prob_sp = predict_with_model(model_sp, test_df)
        
        # 4. Decision Intelligence Layer
        results = test_df.copy()
        results['model_win'] = prob_win
        results['model_place'] = prob_place
        results['model_sp'] = prob_sp
        
        # Dynamic Weighting (Row-wise)
        def apply_dynamic(row):
            # Safe access (defaults if cols missing in raw df, though builder puts them)
            surf = row.get('surface', 'Unknown')
            dist = row.get('distance', 0)
            score, w = calculate_dynamic_score(
                row['model_win'], row['model_place'], row['model_sp'],
                surf, dist
            )
            return pd.Series([score, w['win'], w['place'], w['sp']])

        dyn_res = results.apply(apply_dynamic, axis=1)
        dyn_res.columns = ['final_score', 'w_win', 'w_place', 'w_sp']
        results = pd.concat([results, dyn_res], axis=1)
        
        # Risk Scoring (Race-wise)
        race_risk_list = []
        # Group by City+RaceNo unique key for the day
        for (city, race_no), group in results.groupby(['city', 'race_no']):
            risk = classify_race_risk(group, win_col='model_win')
            risk['city'] = city
            risk['race_no'] = race_no
            race_risk_list.append(risk)
            
        if race_risk_list:
            risk_df = pd.DataFrame(race_risk_list)
            results = pd.merge(results, risk_df, on=['city', 'race_no'], how='left')
        
        # Ranking
        results['pred_rank'] = results.groupby(['city', 'race_no'])['final_score'].rank(method='first', ascending=False)
        
        # 5. Evaluate (Daily Metrics)
        metrics = self.calculate_daily_metrics(results)
        
        # 6. Save Outputs
        date_str = sim_date.isoformat()
        
        # CSV Predictions
        cols = [
            'city', 'race_no', 'horse', 'jockey', 'rank', 'pred_rank', 
            'final_score', 'race_risk_label', 'model_win', 'agf', 'ganyan'
        ]
        out_cols = [c for c in cols if c in results.columns]
        results[out_cols].to_csv(f"{self.daily_dir}/{date_str}_predictions.csv", index=False)
        
        # JSON Metrics
        with open(f"{self.daily_dir}/{date_str}_metrics.json", "w") as f:
            json.dump(metrics, f, indent=4)
            
    def calculate_daily_metrics(self, df):
        # Global Winners
        winners = df[df['rank'] == 1]
        n_races = len(winners)
        if n_races == 0: return {}
        
        hit1 = len(winners[winners['pred_rank'] == 1])
        hit3 = len(winners[winners['pred_rank'] <= 3])
        hit5 = len(winners[winners['pred_rank'] <= 5])
        surprises = len(winners[winners['pred_rank'] >= 7])
        
        metrics = {
            "races": n_races,
            "hit_rate_top1": hit1 / n_races,
            "hit_rate_top3": hit3 / n_races,
            "hit_rate_top5": hit5 / n_races,
            "surprise_winners_missed": surprises,
            "risk_breakdown": {}
        }
        
        # Risk Breakdown
        if 'race_risk_label' in df.columns:
            # Group by risk label (using the full rows, filtered by winners to check hits)
            # Actually easier to use the 'winners' df, but we need total races per label too.
            
            # 1. Counts per label (each race has 1 winner, so len(winners_sub) == races_sub)
            for label, group in winners.groupby('race_risk_label'):
                r_count = len(group)
                r_hit1 = len(group[group['pred_rank'] == 1])
                r_hit3 = len(group[group['pred_rank'] <= 3])
                
                metrics["risk_breakdown"][label] = {
                    "count": r_count,
                    "hit1": r_hit1 / r_count if r_count > 0 else 0,
                    "hit3": r_hit3 / r_count if r_count > 0 else 0
                }
                
        return metrics
