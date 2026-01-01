import pandas as pd
import glob
import os

OUTPUT_DIR = "outputs"
DAILY_REPORTS_DIR = "outputs/daily_reports"

def generate_risk_summary():
    """
    Extracts race-level risk metrics from daily reports and saves a summary CSV.
    """
    print("📋 GENERATING RISK SUMMARY...")
    
    files = glob.glob(f"{DAILY_REPORTS_DIR}/*.csv")
    if not files:
        print("❌ No data found.")
        return

    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    
    # Required columns
    cols = ['date', 'city', 'race_no', 'race_risk_label', 'race_entropy', 'top1_top2_gap']
    
    # Check if 'date' is in columns (it might not be if runner doesn't save it explicitly, usually filename has date)
    # Runner saves: city, race_no, etc. Date comes from filename usually.
    # Let's see if 'date' is in the CSV. 'runner.py' saves `test_df.copy()`. `full_df` has date.
    # So yes, date should be there.
    
    missing = [c for c in cols if c not in df.columns]
    if missing:
        print(f"⚠️ Missing columns for risk summary: {missing}")
        return
        
    # Group by race to get unique rows (since metrics are broadcasted)
    summary = df[cols].drop_duplicates().sort_values(['date', 'city', 'race_no'])
    
    out_path = f"{OUTPUT_DIR}/race_risk_summary.csv"
    summary.to_csv(out_path, index=False)
    
    print(f"✅ Risk Summary saved to {out_path}")
    print("\nRisk Label Distribution:")
    print(summary['race_risk_label'].value_counts())

if __name__ == "__main__":
    generate_risk_summary()
