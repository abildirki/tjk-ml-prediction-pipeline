import pandas as pd
import glob
import os
import json

OUTPUT_DIR = "outputs"
DAILY_REPORTS_DIR = "outputs/daily_reports"

def analyze_surprise_dna():
    """
    Analyzes the characteristics of 'Surprise Winners' vs 'Expected Winners'.
    """
    print("🧬 ANALYZING SURPRISE DNA...")
    
    # 1. Load Data
    files = glob.glob(f"{DAILY_REPORTS_DIR}/*.csv")
    if not files:
        print("❌ No data found.")
        return

    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    
    # Ensure numeric
    cols_to_num = ['rank', 'pred_rank', 'model_prob_top3', 'agf', 'distance']
    for c in cols_to_num:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')
            
    # Filter Winners
    winners = df[df['rank'] == 1].copy()
    
    if len(winners) == 0:
        print("❌ No winners found in data.")
        return

    # 2. Segment
    # Surprise: Rank 1, Pred >= 7
    # Expected: Rank 1, Pred <= 3
    surprise_mask = winners['pred_rank'] >= 7
    expected_mask = winners['pred_rank'] <= 3
    
    surprises = winners[surprise_mask]
    expected = winners[expected_mask]
    
    print(f"📊 Total Winners: {len(winners)}")
    print(f"🔹 Surprise Winners (Model Rank >= 7): {len(surprises)} ({len(surprises)/len(winners):.1%})")
    print(f"🔹 Expected Winners (Model Rank <= 3): {len(expected)} ({len(expected)/len(winners):.1%})")
    
    analysis = {
        "count": {
            "surprise": len(surprises),
            "expected": len(expected)
        }
    }
    
    # 3. AGF Analysis
    print("\n💰 AGF & Ganyan Stats:")
    agf_stats = {
        "surprise_agf_mean": surprises['agf'].mean(),
        "expected_agf_mean": expected['agf'].mean(),
        "surprise_ganyan_mean": surprises['ganyan'].apply(lambda x: float(str(x).replace(',','.')) if pd.notnull(x) else 0).mean()
    }
    print(f"  Surprise Mean AGF: {agf_stats['surprise_agf_mean']:.2f}")
    print(f"  Expected Mean AGF: {agf_stats['expected_agf_mean']:.2f}")
    
    # 4. Track & Distance
    if 'distance' in df.columns:
        def dist_bucket(d):
            if d < 1300: return 'Sprint (<1300)'
            if d <= 1700: return 'Mile (1300-1700)'
            return 'Long (>1700)'
            
        print("\n📏 Distance Breakdown (Surprises):")
        dist_counts = surprises['distance'].apply(dist_bucket).value_counts(normalize=True)
        print(dist_counts.to_string())
    
    if 'surface' in df.columns:
        print("\n🌱 Surface Breakdown (Surprises):")
        surf_counts = surprises['surface'].value_counts(normalize=True)
        print(surf_counts.to_string())
        
    # 5. Jockey
    print("\n🏇 Top Surprise Jockeys:")
    jockey_counts = surprises['jockey'].value_counts().head(5)
    print(jockey_counts.to_string())
    
    # 6. Relative Features
    feats = ['relative_weight', 'relative_hp', 'hp_rank_in_race', 'field_size']
    print("\n📈 Feature Comparison (Mean):")
    print(f"{'Feature':<20} | {'Surprise':<10} | {'Expected':<10}")
    print("-" * 45)
    
    for f in feats:
        if f in df.columns:
            s_val = surprises[f].mean()
            e_val = expected[f].mean()
            print(f"{f:<20} | {s_val:<10.2f} | {e_val:<10.2f}")
            
if __name__ == "__main__":
    analyze_surprise_dna()
