import pandas as pd
import os
from datetime import timedelta
from tjk.features.builder import build_features_for_dataset
from tjk.ml.train import (
    train_place_model, train_win_model, train_sp_model, 
    predict_with_model, FEATURE_COLS
)
from tjk.decision.weighting import calculate_dynamic_score
from tjk.decision.risk import classify_race_risk

OUTPUT_DIR = "outputs/daily_reports"

def run_daily_backtest(start_date, end_date):
    """
    Walk-forward backtest.
    1. Load ALL data (to enable history calcs).
    2. Loop dates [start_date, end_date].
    3. Train on date < current_date.
    4. Predict current_date.
    5. Save report.
    """
    print(f"🚀 STARTING BACKTEST: {start_date} -> {end_date}")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 1. Build Full Dataset (Features)
    # We load slightly before start_date to allow history calculation, 
    # but `load_raw_data` already fetches full DB if args are None.
    # Let's load everything for simplicity (DB is small).
    full_df = build_features_for_dataset()
    
    # Filter for relevant range loop
    # We need a train set (before start) and test set (in range)
    
    # Get unique dates in range sorted
    mask_range = (full_df['date'] >= pd.to_datetime(start_date)) & (full_df['date'] <= pd.to_datetime(end_date))
    test_dates = full_df.loc[mask_range, 'date'].dt.date.unique()
    test_dates = sorted(test_dates)
    
    if not test_dates:
        print("❌ No race dates found in range!")
        return
        
    print(f"📅 Testing on {len(test_dates)} race days...")
    
    all_results = []
    
    for i, current_date in enumerate(test_dates):
        current_ts = pd.to_datetime(current_date)
        
        # A. Split Train/Test
        # Train: Strictly BEFORE current_date
        train_mask = full_df['date'] < current_ts
        test_mask = full_df['date'] == current_ts
        
        train_df = full_df[train_mask]
        test_df = full_df[test_mask]
        
        if len(train_df) < 100:
            print(f"⚠️ Skipping {current_date}: Not enough training data ({len(train_df)} rows).")
            continue
            
        print(f" [{i+1}/{len(test_dates)}] Simulating {current_date}... (Train: {len(train_df)} rows)")
        
        # B. Train Models (Win, Place, SP)
        model_win = train_win_model(train_df)
        model_place = train_place_model(train_df)
        model_sp = train_sp_model(train_df)
        
        # C. Predict
        prob_win = predict_with_model(model_win, test_df)
        prob_place = predict_with_model(model_place, test_df)
        prob_sp = predict_with_model(model_sp, test_df)
        
        # D. Store Results
        # Create result row with metadata
        results = test_df.copy()
        
        results['model_win'] = prob_win
        results['model_place'] = prob_place
        results['model_sp'] = prob_sp
        
        # --- PHASE 4: DYNAMIC WEIGHTING ---
        # Apply row-wise
        # We need to broadcast the calculation.
        # Efficient way: apply per row or vectorize?
        # Since logic is simple (if/else on scalar cols), apply is fine for this scale (~5000 rows).
        
        def apply_dynamic(row):
            score, weights = calculate_dynamic_score(
                row['model_win'], row['model_place'], row['model_sp'],
                row['surface'], row['distance']
            )
            return pd.Series([score, weights['win'], weights['place'], weights['sp']])

        # Result cols: final_score_dynamic, w_win, w_place, w_sp
        dyn_results = results.apply(apply_dynamic, axis=1)
        dyn_results.columns = ['final_score_dynamic', 'win_weight', 'place_weight', 'sp_weight']
        
        results = pd.concat([results, dyn_results], axis=1)
        
        # Legacy/Compat: Use dynamic score for ranking
        results['final_score'] = results['final_score_dynamic'] # Update 'final_score' to dynamic one
        results['model_prob_top3'] = results['final_score_dynamic'] 
        
        # --- PHASE 5: RISK SCORING (RACE LEVEL) ---
        race_risks = []
        # Group by City+RaceNo
        # Note: 'race_no' is not unique globally, only per city/date. 
        # Since we are inside a single date loop, (city, race_no) is unique key.
        
        grouped = results.groupby(['city', 'race_no'])
        for name, group in grouped:
            risk_metrics = classify_race_risk(group, win_col='model_win')
            # Add keys to merge back
            risk_metrics['city'] = name[0]
            risk_metrics['race_no'] = name[1]
            race_risks.append(risk_metrics)
            
        df_risks = pd.DataFrame(race_risks)
        
        # Merge risk metrics back to results (broadcast to all horses in race)
        if not df_risks.empty:
            results = pd.merge(results, df_risks, on=['city', 'race_no'], how='left')
        else:
             # Should not happen
            results['race_risk_label'] = 'UNKNOWN'
            results['race_entropy'] = 0.0
            results['top1_top2_gap'] = 0.0

        # Pred Rank (Sort by Dynamic Score)
        results['pred_rank'] = results.groupby(['city', 'race_no'])['final_score'].rank(method='first', ascending=False)
        
        # Save Daily Report
        report_path = f"{OUTPUT_DIR}/{current_date}.csv"
        # Select nice cols
        out_cols = [
            'city', 'race_no', 'horse', 'jockey', 'rank', 'pred_rank', 
            'model_prob_top3', 'final_score', 
            'race_risk_label', 'race_entropy', 'top1_top2_gap', # Risk
            'win_weight', 'place_weight', 'sp_weight', # Weights
            'model_win', 'model_place', 'model_sp', # Raw models
            'agf', 'ganyan', 'distance', 'surface'
        ] + [c for c in FEATURE_COLS if c in results.columns]
        
        results[out_cols].to_csv(report_path, index=False)
        all_results.append(results)
        
    print("✅ Backtest Complete.")
