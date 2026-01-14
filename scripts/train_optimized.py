
import sys
import os
import pandas as pd
import numpy as np
from datetime import date, timedelta

# Add src to path
if "src" not in sys.path:
    sys.path.append(os.path.join(os.getcwd(), "src"))

from tjk.ml.dataset import load_raw_data, prepare_features
from tjk.ml.train import predict_with_model, train_place_model, train_win_model, train_sp_model, FEATURE_COLS
from tjk.coupon_generator import CouponGenerator # We will mimic logic, not use class directly to avoid scraping

import joblib
from sklearn.model_selection import RandomizedSearchCV
import xgboost as xgb

def optimize_and_train():
    print("🧠 Starting Smart Optimization & Retraining...")

    # 1. Load Data
    df = load_raw_data()
    if df.empty:
        print("❌ No data.")
        return

    # 2. Feature Engineering
    df = prepare_features(df)

    # 3. Train/Test Split (Time-based)
    # We want to train on past, validate on recent
    cutoff_date = df['race_date'].max() - pd.Timedelta(days=60)

    train_df = df[df['race_date'] <= cutoff_date].copy()
    val_df = df[df['race_date'] > cutoff_date].copy()

    print(f"📊 Training on {len(train_df)} rows, Validating on {len(val_df)} rows.")

    X_train = train_df[FEATURE_COLS]
    y_train = (train_df['rank'] == 1).astype(int)

    X_val = val_df[FEATURE_COLS]
    y_val = (val_df['rank'] == 1).astype(int)

    # 4. Hyperparameter Tuning (Random Search)
    # XGBoost Params
    param_grid = {
        'n_estimators': [100, 200, 300],
        'max_depth': [3, 4, 5, 6],
        'learning_rate': [0.01, 0.05, 0.1],
        'subsample': [0.7, 0.8, 1.0],
        'colsample_bytree': [0.7, 0.8, 1.0],
        'scale_pos_weight': [1, 5, 10] # Handle imbalance
    }

    print("🔍 Tuning Hyperparameters for Win Model...")
    xgb_model = xgb.XGBClassifier(objective='binary:logistic', eval_metric='logloss', tree_method='hist')

    search = RandomizedSearchCV(
        xgb_model,
        param_distributions=param_grid,
        n_iter=10,
        scoring='roc_auc',
        cv=3,
        verbose=1,
        n_jobs=-1
    )

    search.fit(X_train, y_train)

    best_model = search.best_estimator_
    print(f"✅ Best Params: {search.best_params_}")
    print(f"✅ Best CV Score: {search.best_score_:.4f}")

    # 5. Evaluate on Validation Set
    val_probs = best_model.predict_proba(X_val)[:, 1]

    # Check Top 1 Accuracy in Val Set
    val_df['prob_win'] = val_probs

    # Group by Race
    val_df['race_id_unique'] = val_df['race_date'].astype(str) + val_df['city'] + val_df['race_no'].astype(str)

    correct_wins = 0
    total_races = 0

    error_cases = []

    for rid, grp in val_df.groupby('race_id_unique'):
        top_pick = grp.sort_values('prob_win', ascending=False).iloc[0]
        actual_winner = grp[grp['rank'] == 1]

        if not actual_winner.empty:
            total_races += 1
            if top_pick['rank'] == 1:
                correct_wins += 1
            else:
                # Log Error
                winner = actual_winner.iloc[0]
                error_cases.append({
                    'race': rid,
                    'predicted': top_pick['horse_name'],
                    'pred_prob': top_pick['prob_win'],
                    'winner': winner['horse_name'],
                    'winner_prob': winner['prob_win'],
                    'winner_agf': winner['agf'],
                    'winner_ganyan': winner['ganyan']
                })

    acc = correct_wins / total_races if total_races > 0 else 0
    print(f"🏆 Validation Top-1 Accuracy: {acc*100:.2f}% ({correct_wins}/{total_races})")

    # 6. Save Error Analysis
    if error_cases:
        err_df = pd.DataFrame(error_cases)
        err_df.to_csv("outputs/backtest/error_analysis.csv", index=False)
        print("📉 Error analysis saved to outputs/backtest/error_analysis.csv")

        # Insight: What implies a miss?
        avg_miss_agf = pd.to_numeric(err_df['winner_agf'], errors='coerce').mean()
        print(f"💡 Average AGF of missed winners: {avg_miss_agf:.2f} (Low AGF = Surprise)")

    # 7. Final Training (Full Data) & Save
    print("🚀 Retraining all models on full dataset with optimized params...")

    # Apply best params to Win Model
    final_win_model = xgb.XGBClassifier(**search.best_params_, objective='binary:logistic', eval_metric='logloss')
    final_win_model.fit(df[FEATURE_COLS], (df['rank']==1).astype(int))

    # Standard Place/Sp Models (Can optimize similarly, but sticking to logic)
    # Note: SP model logic handles weighting manually in code, let's keep train_sp_model but pass params if needed?
    # For now, just retrain them as is.
    final_place_model = train_place_model(df)
    final_sp_model = train_sp_model(df)

    MODEL_DIR = "outputs/models"
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(final_place_model, os.path.join(MODEL_DIR, "xgb_place.pkl"))
    joblib.dump(final_win_model, os.path.join(MODEL_DIR, "xgb_win.pkl"))
    joblib.dump(final_sp_model, os.path.join(MODEL_DIR, "xgb_sp.pkl"))
    print("✅ Models Updated.")

if __name__ == "__main__":
    optimize_and_train()
