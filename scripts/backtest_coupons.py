
import sys
import os
import pandas as pd
import numpy as np
import joblib

if "src" not in sys.path:
    sys.path.append(os.path.join(os.getcwd(), "src"))

from tjk.ml.dataset import load_raw_data, prepare_features
from tjk.ml.train import predict_with_model

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

def generate_coupon_for_race_group(race_data, race_nos):
    """
    Simulates Coupon Generation Logic (Eco/Wide) for a set of races.
    Returns: Is_Winner_In_Eco, Is_Winner_In_Wide, Coupon_Cost
    """
    eco_legs = []
    wide_legs = []

    # 1. Determine Selections
    for r_no in race_nos:
        # Get runners for this race
        runners = race_data[race_data['race_no'] == r_no].copy()
        runners = runners.sort_values('prob_win', ascending=False)

        # Banko Logic
        top1 = runners.iloc[0]
        win_prob = top1['prob_win']

        is_banko = win_prob > 0.45 # Threshold

        # Eco Selection
        eco_sel = []
        if is_banko:
            eco_sel = [top1['horse_name']]
        else:
            # Take top 3
            eco_sel = runners.iloc[:3]['horse_name'].tolist()

        # Wide Selection
        wide_sel = []
        if is_banko:
            wide_sel = [top1['horse_name']]
        else:
            # Take top 5 + Surprise
            base = runners.iloc[:5]['horse_name'].tolist()
            # Add surprise
            surprises = runners[runners['prob_sp'] > 0.5]['horse_name'].tolist()
            wide_sel = list(set(base + surprises))

        eco_legs.append(eco_sel)
        wide_legs.append(wide_sel)

    # 2. Check Success
    eco_win = True
    wide_win = True

    for i, r_no in enumerate(race_nos):
        runners = race_data[race_data['race_no'] == r_no]
        winner = runners[runners['rank'] == 1]
        if winner.empty:
            continue # Race cancelled or no result?

        winner_name = winner.iloc[0]['horse_name']

        if winner_name not in eco_legs[i]:
            eco_win = False
        if winner_name not in wide_legs[i]:
            wide_win = False

    # Cost (approx 1 unit per combination)
    # Combinations = len(leg1) * len(leg2) ...
    eco_cost = np.prod([len(l) for l in eco_legs])
    wide_cost = np.prod([len(l) for l in wide_legs])

    return eco_win, wide_win, eco_cost, wide_cost

def backtest_coupons():
    print("🎫 Starting Historical Coupon Backtest...")

    # 1. Load & Prep
    df = load_raw_data()
    if df.empty: return
    df = prepare_features(df)

    place_model, win_model, sp_model = load_models_local()
    df['prob_win'] = predict_with_model(win_model, df)
    df['prob_sp'] = predict_with_model(sp_model, df)

    # Filter Test Set
    cutoff_date = df['race_date'].max() - pd.Timedelta(days=30)
    test_df = df[df['race_date'] > cutoff_date].copy()

    print(f"Checking coupons for {test_df['race_date'].nunique()} days...")

    results = []

    # Group by Date & City
    for (d, city), day_data in test_df.groupby(['race_date', 'city']):
        # Find 6-Ganyan legs (e.g. 1-6 or 4-9)
        races = sorted(day_data['race_no'].unique())

        target_legs = []
        if set(range(1, 7)).issubset(races):
            target_legs = list(range(1, 7))
        elif set(range(4, 10)).issubset(races):
            target_legs = list(range(4, 10))
        elif len(races) >= 6:
            target_legs = races[-6:]
        else:
            continue # Not enough races

        # Generate & Check
        eco_w, wide_w, eco_c, wide_c = generate_coupon_for_race_group(day_data, target_legs)

        results.append({
            'date': d,
            'city': city,
            'eco_win': eco_w,
            'wide_win': wide_w,
            'eco_cost': eco_c,
            'wide_cost': wide_c
        })

    # Report
    res_df = pd.DataFrame(results)
    if res_df.empty:
        print("No valid programs found.")
        return

    print("\n📊 --- COUPON CONSISTENCY REPORT ---")
    print(f"Total Programs : {len(res_df)}")
    print(f"Eco Success    : {res_df['eco_win'].mean()*100:.1f}%")
    print(f"Wide Success   : {res_df['wide_win'].mean()*100:.1f}%")
    print(f"Avg Eco Cost   : {res_df['eco_cost'].mean():.1f} Units")
    print(f"Avg Wide Cost  : {res_df['wide_cost'].mean():.1f} Units")

    res_df.to_csv("outputs/backtest/coupon_consistency.csv", index=False)
    print("💾 Saved to outputs/backtest/coupon_consistency.csv")

if __name__ == "__main__":
    backtest_coupons()
