
import os
import sys
import pandas as pd
import joblib
from datetime import date

# Ensure we can find src
if "src" not in sys.path:
    sys.path.append(os.path.join(os.getcwd(), "src"))

from tjk.ml.dataset import load_raw_data, prepare_features
from tjk.ml.train import predict_with_model

MODEL_DIR = "outputs/models"

def load_models(model_dir=MODEL_DIR):
    """Loads trained ML models from disk."""
    try:
        place_model = joblib.load(os.path.join(model_dir, "xgb_place.pkl"))
        win_model = joblib.load(os.path.join(model_dir, "xgb_win.pkl"))
        sp_model = joblib.load(os.path.join(model_dir, "xgb_sp.pkl"))
        return place_model, win_model, sp_model
    except Exception as e:
        print(f"Error loading models from {model_dir}: {e}")
        return None, None, None

def get_predictions_for_date(target_date: date, city: str = None):
    """
    Generates predictions for a specific date (and optional city).
    Returns a DataFrame with columns: [horse_name, prob_win, prob_place, prob_sp, ...]
    """
    # 1. Load Data
    # We load everything to get history for feature engineering
    df = load_raw_data()

    if df.empty:
        return None

    # 2. Feature Engineering
    df = prepare_features(df)

    # 3. Filter for Target
    # Ensure date type match
    df['date'] = pd.to_datetime(df['race_date']).dt.date
    program = df[df['date'] == target_date].copy()

    if city:
        # Normalize city check (basic)
        program = program[program['city'].str.contains(city, case=False, na=False)]

    if program.empty:
        return pd.DataFrame() # Empty result

    # 4. Load Models & Predict
    place_model, win_model, sp_model = load_models()

    if not win_model:
        raise FileNotFoundError("Models not trained. Please train first.")

    program['prob_win'] = predict_with_model(win_model, program)
    program['prob_place'] = predict_with_model(place_model, program)
    program['prob_sp'] = predict_with_model(sp_model, program)

    return program
