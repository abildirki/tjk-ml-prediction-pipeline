import pandas as pd
import numpy as np
import glob
import os
import json
from sklearn.metrics import roc_auc_score, log_loss
from tjk.features.builder import build_features_for_dataset
from tjk.ml.train import train_xgboost_model, FEATURE_COLS

OUTPUT_DIR = "outputs"
DAILY_REPORTS_DIR = "outputs/daily_reports"

def load_backtest_results():
    """
    Loads all daily CSV reports into a single DataFrame.
    """
    files = glob.glob(f"{DAILY_REPORTS_DIR}/*.csv")
    if not files:
        print("❌ No backtest reports found!")
        return None
        
    dfs = []
    for f in files:
        dfs.append(pd.read_csv(f))
        
    full_df = pd.concat(dfs, ignore_index=True)
    return full_df

def calculate_classification_metrics(df):
    """
    Calculates AUC and LogLoss for Win (Rank=1) and Place (Rank<=3).
    """
    metrics = {}
    
    # 1. Win Metrics
    y_true_win = (df['rank'] == 1).astype(int)
    # XGBoost output is prob of being Top 3 (Place), not necessarily Win.
    # But usually higher prob implies higher win chance.
    # Ideally, we should have separate models, but let's evaluate 'model_prob_top3' for Win correlation.
    
    try:
        metrics['win_auc'] = roc_auc_score(y_true_win, df['model_prob_top3'])
        metrics['win_logloss'] = log_loss(y_true_win, df['model_prob_top3'])
    except:
        metrics['win_auc'] = 0.0
        metrics['win_logloss'] = 0.0

    # 2. Place Metrics (Rank <= 3)
    # This is what the model was actually trained for (is_top3 target).
    y_true_place = (df['rank'] <= 3).astype(int)
    
    try:
        metrics['place_auc'] = roc_auc_score(y_true_place, df['model_prob_top3'])
        metrics['place_logloss'] = log_loss(y_true_place, df['model_prob_top3'])
    except:
        metrics['place_auc'] = 0.0
        metrics['place_logloss'] = 0.0
        
    return metrics

def calculate_ranking_metrics(df):
    """
    Calculates Hit Rates based on `pred_rank`.
    """
    # Filter for winners
    winners = df[df['rank'] == 1]
    total_races = len(winners) # Assuming 1 winner per race (mostly true)
    
    if total_races == 0:
        return {}
        
    hit_at_1 = len(winners[winners['pred_rank'] == 1])
    hit_at_3 = len(winners[winners['pred_rank'] <= 3])
    hit_at_5 = len(winners[winners['pred_rank'] <= 5])
    
    return {
        "hit_rate@1": hit_at_1 / total_races,
        "hit_rate@3": hit_at_3 / total_races,
        "hit_rate@5": hit_at_5 / total_races,
        "total_races": total_races
    }

def analyze_surprises(df):
    """
    Identifies winners that the model missed (Predicted Rank >= 7).
    """
    # Winners where we predicted them deeply.
    surprise_mask = (df['rank'] == 1) & (df['pred_rank'] >= 7)
    surprises = df[surprise_mask].copy()
    
    # Select strictly relevant columns
    cols = ['date', 'city', 'race_no', 'horse', 'pred_rank', 'model_prob_top3', 'actual_rank', 'agf', 'ganyan']
    # Add rank/actual_rank alias if needed, but 'rank' is the raw column.
    
    # Guard for missing cols
    out_cols = [c for c in cols if c in surprises.columns]
    
    return surprises[out_cols]

def calculate_feature_importance():
    """
    Trains a fresh model on ALL data to extract global feature importance.
    """
    print("⏳ Training standard model for Feature Importance...")
    df = build_features_for_dataset() # Load full history
    model = train_xgboost_model(df)
    
    importance = model.get_booster().get_score(importance_type='gain')
    # Convert to DF
    imp_df = pd.DataFrame(list(importance.items()), columns=['Feature', 'Gain'])
    imp_df = imp_df.sort_values('Gain', ascending=False)
    
    return imp_df

def run_evaluation():
    print("📊 STARTING EVALUATION...")
    
    # A. Load Data
    df = load_backtest_results()
    if df is None: return

    print(f"✅ Loaded {len(df)} output rows.")
    
    # B. Metrics
    clf_metrics = calculate_classification_metrics(df)
    rank_metrics = calculate_ranking_metrics(df)
    
    summary = {**clf_metrics, **rank_metrics}
    
    # C. Surprises
    surprises = analyze_surprises(df)
    summary['surprise_total'] = len(surprises)
    if rank_metrics.get('total_races', 0) > 0:
        summary['surprise_rate'] = len(surprises) / rank_metrics['total_races']
    
    # D. Feature Importance
    feat_imp = calculate_feature_importance()
    
    # SAVE OUTPUTS
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 1. Summary JSON
    with open(f"{OUTPUT_DIR}/summary_metrics.json", "w") as f:
        json.dump(summary, f, indent=4)
        
    # 2. Case Studies (Surprises)
    surprises.to_csv(f"{OUTPUT_DIR}/case_studies.csv", index=False)
    
    # 3. Feature Importance
    feat_imp.to_csv(f"{OUTPUT_DIR}/feature_importance.csv", index=False)
    
    print("\n📈 EVALUATION REPORT:")
    print(json.dumps(summary, indent=4))
    print(f"\n📂 Outputs saved to {OUTPUT_DIR}/")
