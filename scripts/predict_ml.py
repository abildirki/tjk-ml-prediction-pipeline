
import sys
import os
import pandas as pd
import joblib
from datetime import date, timedelta

# Add src to path so we can import tjk modules
sys.path.append(os.path.join(os.getcwd(), "src"))

from tjk.ml.dataset import load_raw_data, prepare_features
from tjk.ml.train import train_place_model, train_win_model, train_sp_model, predict_with_model, FEATURE_COLS

MODEL_DIR = "outputs/models"
os.makedirs(MODEL_DIR, exist_ok=True)

def train_and_save():
    print("🚀 Starting Training Process...")

    # 1. Load Data
    # Training on historical data (e.g., up to yesterday)
    # For this demo, we load everything. In prod, use a cutoff date.
    df = load_raw_data(end_date=str(date.today() - timedelta(days=1)))

    if df.empty:
        print("❌ No data found for training.")
        return

    # 2. Feature Engineering
    df = prepare_features(df)

    # 3. Train Models
    print("🧠 Training Place Model (Top 3)...")
    place_model = train_place_model(df)

    print("🧠 Training Win Model (Top 1)...")
    win_model = train_win_model(df)

    print("🧠 Training Surprise Model (Win + Low AGF)...")
    sp_model = train_sp_model(df)

    # 4. Save
    print(f"💾 Saving models to {MODEL_DIR}...")
    joblib.dump(place_model, os.path.join(MODEL_DIR, "xgb_place.pkl"))
    joblib.dump(win_model, os.path.join(MODEL_DIR, "xgb_win.pkl"))
    joblib.dump(sp_model, os.path.join(MODEL_DIR, "xgb_sp.pkl"))
    print("✅ Training Complete.")

def load_models():
    try:
        place_model = joblib.load(os.path.join(MODEL_DIR, "xgb_place.pkl"))
        win_model = joblib.load(os.path.join(MODEL_DIR, "xgb_win.pkl"))
        sp_model = joblib.load(os.path.join(MODEL_DIR, "xgb_sp.pkl"))
        return place_model, win_model, sp_model
    except FileNotFoundError:
        print("⚠️ Models not found. Training now...")
        train_and_save()
        return load_models()

def predict_future(target_date=None):
    if not target_date:
        target_date = date.today()

    print(f"🔮 Predicting for {target_date}...")

    # 1. Load Data (History + Today's Program)
    # We need history to calculate features (rolling stats)
    # So we load EVERYTHING, then filter for today.
    # Ideally, we would cache features, but for now we recalculate.
    df = load_raw_data() # Loads everything including today's entries if scraped

    if df.empty:
        print("❌ No data found.")
        return

    # 2. Feature Engineering
    df = prepare_features(df)

    # 3. Filter for Target Date
    # Check data types
    df['date'] = pd.to_datetime(df['race_date']).dt.date
    program = df[df['date'] == target_date].copy()

    if program.empty:
        print(f"❌ No races found for {target_date}. Did you scrape today's program?")
        return

    # 4. Predict
    place_model, win_model, sp_model = load_models()

    program['prob_win'] = predict_with_model(win_model, program)
    program['prob_place'] = predict_with_model(place_model, program)
    program['prob_sp'] = predict_with_model(sp_model, program)

    # 5. Report
    output_file = f"prediction_ml_{target_date}.md"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"# 🤖 AI Predictions for {target_date}\n\n")
        f.write("Models: XGBoost (Win, Place, Surprise)\n\n")

        # Group by City -> Race
        for city in program['city'].unique():
            f.write(f"## 🏙️ {city}\n\n")
            city_df = program[program['city'] == city]

            for race_no in sorted(city_df['race_no'].unique()):
                r_df = city_df[city_df['race_no'] == race_no].copy()
                meta = r_df.iloc[0]
                f.write(f"### Race {race_no} - {meta['distance_m']}m {meta['surface']}\n")

                # Sort by Win Probability
                r_df = r_df.sort_values('prob_win', ascending=False)

                f.write("| Rank | Horse | Jockey | Win % | Place % | Surprise % | HP | Form | AGF |\n")
                f.write("|---|---|---|---|---|---|---|---|---|\n")

                for i, row in enumerate(r_df.itertuples(), 1):
                    win_pct = f"{row.prob_win*100:.1f}%"
                    place_pct = f"{row.prob_place*100:.1f}%"
                    sp_pct = f"{row.prob_sp*100:.1f}%"

                    # Highlight top picks
                    icon = "🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else str(i)

                    # Highlight Surprise Candidates (High SP score)
                    sp_marker = ""
                    if row.prob_sp > 0.5: # Threshold for surprise
                         sp_marker = "⚡"

                    f.write(f"| {icon} | {row.horse_name} {sp_marker} | {row.jockey_name} | **{win_pct}** | {place_pct} | {sp_pct} | {row.hp:.0f} | {row.form_score} | {row.agf} |\n")

                f.write("\n")

    print(f"✅ Predictions saved to {output_file}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "train":
        train_and_save()
    else:
        # Default: Predict for today (or specific date if needed)
        # You can change this to date.today()
        # For testing, we might want a date with data.

        # Check if we need to train first
        if not os.path.exists(os.path.join(MODEL_DIR, "xgb_win.pkl")):
            train_and_save()

        predict_future(date.today())
