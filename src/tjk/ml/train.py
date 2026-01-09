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
    'weight_kg', 'hp' # Changed 'weight' to 'weight_kg' to match DB/Dataset
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
    Target: Rank == 1 AND AGF < 5 (Surprise Winner)
    Goal: Identify 'dark horses' (Low AGF winning horses).

    Definition of Surprise:
    - Winner (Rank = 1)
    - AGF < 5.0 (Low odds/probability according to public)
    """
    X = train_df[FEATURE_COLS].copy()
    
    # Definition of "Surprise": Winner AND Low AGF (e.g. < 5.0)
    # Note: AGF is usually 0-100 (percentage points usually sum to 100 per race).
    # AGF 5 means 5% win chance implied by public.
    SURPRISE_AGF_THRESHOLD = 5.0
    
    is_winner = (train_df['rank'] == 1)
    is_low_agf = (train_df['agf'] < SURPRISE_AGF_THRESHOLD)
    
    y = (is_winner & is_low_agf).astype(int)
    
    # Handle Class Imbalance
    # Surprise winners are rare.
    pos_count = y.sum()
    neg_count = len(y) - pos_count
    scale_pos_weight = neg_count / pos_count if pos_count > 0 else 1.0

    print(f"  > SP Model Training: {pos_count} surprises out of {len(y)} samples.")
    
    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=3, # Shallower tree to prevent overfitting on noise
        learning_rate=0.05,
        objective='binary:logistic',
        eval_metric='logloss',
        use_label_encoder=False,
        tree_method='hist',
        scale_pos_weight=scale_pos_weight # Critical for finding rare events
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
