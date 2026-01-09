
import sys
import os
import pandas as pd
import numpy as np
from datetime import date, timedelta

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from tjk.ml.dataset import load_raw_data, prepare_features
from tjk.ml.train import predict_with_model

# Need to update tjk.ml.train to export load_models or just use joblib here
import joblib

MODEL_DIR = "outputs/models"

def load_models_local():
    try:
        place_model = joblib.load(os.path.join(MODEL_DIR, "xgb_place.pkl"))
        win_model = joblib.load(os.path.join(MODEL_DIR, "xgb_win.pkl"))
        sp_model = joblib.load(os.path.join(MODEL_DIR, "xgb_sp.pkl"))
        return place_model, win_model, sp_model
    except Exception as e:
        print(f"Error loading models: {e}")
        return None, None, None

def simulate_betting():
    print("🎰 Starting Betting Simulation (Backtest)...")

    # 1. Load Data
    # In a real backtest, we should use a "Hold-Out" set (e.g., last 2 months)
    # that the model hasn't seen during training.
    # For now, we use the most recent 1000 races from the DB as a proxy.
    df = load_raw_data()

    if df.empty:
        print("❌ No data.")
        return

    # 2. Feature Engineering
    df = prepare_features(df)

    # 3. Load Models
    place_model, win_model, sp_model = load_models_local()
    if not win_model:
        print("❌ Models not found. Train first.")
        return

    # 4. Filter Test Set (Last 30 Days)
    cutoff_date = df['race_date'].max() - pd.Timedelta(days=30)
    test_df = df[df['race_date'] > cutoff_date].copy()

    if test_df.empty:
        print("❌ Not enough data for backtest.")
        return

    print(f"🧪 Backtesting on {len(test_df)} rows from {cutoff_date.date()} to {df['race_date'].max().date()}")

    # 5. Predict
    test_df['prob_win'] = predict_with_model(win_model, test_df)
    test_df['prob_sp'] = predict_with_model(sp_model, test_df)

    # 6. Simulate Strategy: Bet on Top Model Pick per Race
    # Group by Race

    total_bets = 0
    total_wins = 0
    total_spent = 0
    total_return = 0

    # Standard odd for simulation (since we don't have all odds)
    # We use 'ganyan' column if available, else assume conservative 2.5

    results = []

    # Unique races
    test_df['race_id_unique'] = test_df['race_date'].astype(str) + test_df['city'] + test_df['race_no'].astype(str)

    for race_id, race_data in test_df.groupby('race_id_unique'):
        # Sort by model probability
        race_data = race_data.sort_values('prob_win', ascending=False)
        top_pick = race_data.iloc[0]

        # Bet 1 unit
        bet_amount = 10 # TL
        total_bets += 1
        total_spent += bet_amount

        is_winner = (top_pick['rank'] == 1)

        win_amount = 0
        if is_winner:
            total_wins += 1
            # Parse Ganyan (e.g. "3.45")
            try:
                ganyan = float(top_pick['ganyan'])
            except:
                ganyan = 2.50 # Default/Conservative

            win_amount = bet_amount * ganyan
            total_return += win_amount

        results.append({
            'race': race_id,
            'pick': top_pick['horse_name'],
            'win_prob': top_pick['prob_win'],
            'won': is_winner,
            'ganyan': win_amount/bet_amount if is_winner else 0,
            'profit': win_amount - bet_amount
        })

    # 7. Report
    roi = ((total_return - total_spent) / total_spent) * 100 if total_spent > 0 else 0
    win_rate = (total_wins / total_bets) * 100 if total_bets > 0 else 0

    print("\n📊 --- SIMULATION RESULTS ---")
    print(f"Total Races Bet : {total_bets}")
    print(f"Total Wins      : {total_wins}")
    print(f"Win Rate        : {win_rate:.2f}%")
    print(f"Total Spent     : {total_spent:.2f} TL")
    print(f"Total Return    : {total_return:.2f} TL")
    print(f"Net Profit      : {total_return - total_spent:.2f} TL")
    print(f"ROI             : {roi:.2f}%")

    # Save detailed log
    res_df = pd.DataFrame(results)
    res_df.to_csv("outputs/backtest_simulation.csv", index=False)
    print("💾 Details saved to outputs/backtest_simulation.csv")

if __name__ == "__main__":
    simulate_betting()
