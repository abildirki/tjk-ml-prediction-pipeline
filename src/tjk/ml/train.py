import pandas as pd
import xgboost as xgb
from sklearn.linear_model import LogisticRegression
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

FEATURE_COLS = [
    # History
    'avg_rank_last3', 'avg_rank_last5', 'win_rate_last5', 'place_rate_last5',
    # Specialization
    'same_track_win_rate', 'track_specialization_ratio', 'dist_specialization_ratio',
    # Relative
    'relative_weight', 'relative_hp', 'hp_rank_in_race', 'field_size',
    # Raw
    'weight', 'hp'
]

TARGET_COL = 'is_top3' # Or is_win

def train_baseline_model(train_df):
    """
    Simple Logistic Regression Baseline.
    """
    X = train_df[FEATURE_COLS].copy()
    y = (train_df['rank'] <= 3).astype(int) # Top 3 Target
    
    # Pipeline: Impute -> Scale -> LogReg
    pipe = Pipeline([
        ('imputer', SimpleImputer(strategy='mean')),
        ('scaler', StandardScaler()),
        ('model', LogisticRegression(max_iter=1000))
    ])
    
    pipe.fit(X, y)
    return pipe

def train_xgboost_model(train_df):
    """
    Standard Place Model (Rank <= 3).
    Kept for backward compatibility.
    """
    return train_place_model(train_df)

def train_place_model(train_df):
    """
    Target: Rank <= 3 (Place)
    """
    X = train_df[FEATURE_COLS].copy()
    y = (train_df['rank'] <= 3).astype(int)
    
    model = xgb.XGBClassifier(
        n_estimators=100, max_depth=5, learning_rate=0.05,
        objective='binary:logistic', eval_metric='logloss',
        use_label_encoder=False, tree_method='hist'
    )
    model.fit(X, y)
    return model

def train_win_model(train_df):
    """
    Target: Rank == 1 (Win)
    Goal: Pinpoint the exact winner.
    """
    X = train_df[FEATURE_COLS].copy()
    y = (train_df['rank'] == 1).astype(int)
    
    # Win is harder, maybe simpler tree?
    model = xgb.XGBClassifier(
        n_estimators=100, max_depth=4, learning_rate=0.05,
        objective='binary:logistic', eval_metric='logloss',
        use_label_encoder=False, tree_method='hist'
    )
    model.fit(X, y)
    return model

def train_sp_model(train_df):
    """
    Target: Rank == 1 AND AGF Rank >= 4 (Surprise Winner)
    Goal: Identify 'dark horses'.
    """
    X = train_df[FEATURE_COLS].copy()
    
    # Calculate AGF Rank for labeling
    # Note: We need grouping to get rank.
    # But for simplicity, let's assume AGF < 5.0 (Low odds) vs > 5.0?
    # Or strict 'agf_rank'. 
    
    # Let's derive agf_rank quickly
    # This might be slow if we groupby every time.
    # Vectorized check: AGF < 10% (approx < 10.0 value? No AGF is prob * 100 often? Or implied?)
    # In dataset AGF seems to be 0-100 score? 
    # DNA Analysis showed Expected AGF Mean ~32, Surprise ~10.
    # So AGF < 15 is a reasonable cutoff for "Non-Favorite".
    
    # Proxy Target: Winner AND AGF < 15.0
    is_winner = (train_df['rank'] == 1)
    is_low_agf = (train_df['agf'] < 15.0) 
    # Wait, AGF 10 means 10%? DNA said 10.52 vs 32.67.
    # 32% win prob is high. 10% is low.
    
    y = (is_winner & is_low_agf).astype(int)
    
    # SP Model needs to find needles in haystack. High class imbalance.
    scale_pos_weight = (len(y) - y.sum()) / y.sum() if y.sum() > 0 else 1.0
    
    model = xgb.XGBClassifier(
        n_estimators=100, max_depth=3, learning_rate=0.05, # Shallower tree for stability
        objective='binary:logistic', eval_metric='logloss',
        use_label_encoder=False, tree_method='hist',
        scale_pos_weight=scale_pos_weight # Handle imbalance
    )
    model.fit(X, y)
    return model

def predict_with_model(model, df):
    """
    Returns DataFrame with 'proba' column.
    """
    X = df[FEATURE_COLS].copy()
    
    # Check if pipe or raw model
    # Pipe handles transform
    if hasattr(model, 'predict_proba'):
        # [:, 1] for positive class
        probs = model.predict_proba(X)[:, 1]
        return probs
    else:
        # Should not happen with sklearn/xgb interfaces
        return [0.0] * len(X)
