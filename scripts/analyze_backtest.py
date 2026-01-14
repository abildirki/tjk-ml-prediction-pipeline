import sys
import os
sys.path.append(os.path.join(os.getcwd(), "src"))

import pandas as pd
import os

DAILY_CSV = "outputs/backtest/daily_results.csv"
CITY_SUMMARY_CSV = "outputs/backtest/daily_city_summary.csv"
SUMMARY_REPORT = "outputs/backtest/summary_report.txt"

def analyze():
    if not os.path.exists(DAILY_CSV):
        print(f"File not found: {DAILY_CSV}")
        return

    # 1. Load and Rename
    df = pd.read_csv(DAILY_CSV)
    
    # Check if already renamed to avoid errors if run multiple times
    rename_map = {
        'Is_Scientific_Winner_In_Eco': 'Eco_Has_Winner_In_Leg',
        'Is_Scientific_Winner_In_Wide': 'Wide_Has_Winner_In_Leg'
    }
    df.rename(columns=rename_map, inplace=True)
    
    # Save back (overwrite)
    df.to_csv(DAILY_CSV, index=False)
    print(f"✅ Renamed columns in {DAILY_CSV}")
    
    # 2. Daily City Summary
    # Group by Date, City
    # We assume 'Race' count is the Total Legs
    
    # Aggregations
    # Banko counts need sum
    # Win checks need sum
    
    grouped = df.groupby(['Date', 'City']).agg({
        'Race': 'count',
        'Eco_Has_Winner_In_Leg': 'sum',
        'Wide_Has_Winner_In_Leg': 'sum',
        'Banko_Horse': 'count', # Count of non-null bankos
        'Banko_Win': 'sum',
        'Banko_Top3': 'sum'
    }).reset_index()
    
    grouped.rename(columns={'Race': 'Total_Legs'}, inplace=True)
    
    # Derived Metrics
    grouped['Eco_Ticket_Pass'] = (grouped['Eco_Has_Winner_In_Leg'] == grouped['Total_Legs']).astype(int)
    grouped['Wide_Ticket_Pass'] = (grouped['Wide_Has_Winner_In_Leg'] == grouped['Total_Legs']).astype(int)
    
    grouped['Eco_Miss_Count'] = grouped['Total_Legs'] - grouped['Eco_Has_Winner_In_Leg']
    grouped['Wide_Miss_Count'] = grouped['Total_Legs'] - grouped['Wide_Has_Winner_In_Leg']
    
    # Save City Summary
    grouped.to_csv(CITY_SUMMARY_CSV, index=False)
    print(f"✅ Generated {CITY_SUMMARY_CSV}")
    
    # 3. Overall Summary
    total_days = df['Date'].nunique()
    total_city_programs = len(grouped)
    total_races = len(df)
    
    # Banko Stats
    total_banko_assigned = grouped['Banko_Horse'].sum()
    total_banko_won = grouped['Banko_Win'].sum()
    total_banko_top3 = grouped['Banko_Top3'].sum()
    
    banko_win_rate = (total_banko_won / total_banko_assigned * 100) if total_banko_assigned else 0
    banko_place_rate = (total_banko_top3 / total_banko_assigned * 100) if total_banko_assigned else 0
    
    # Coupon Stats (Ticket Level)
    eco_tickets_won = grouped['Eco_Ticket_Pass'].sum()
    wide_tickets_won = grouped['Wide_Ticket_Pass'].sum()
    
    eco_ticket_rate = (eco_tickets_won / total_city_programs * 100) if total_city_programs else 0
    wide_ticket_rate = (wide_tickets_won / total_city_programs * 100) if total_city_programs else 0
    
    # Leg Stats (Race Level)
    avg_eco_legs = grouped['Eco_Has_Winner_In_Leg'].mean()
    avg_wide_legs = grouped['Wide_Has_Winner_In_Leg'].mean()
    avg_total_legs = grouped['Total_Legs'].mean()
    
    eco_leg_rate = (df['Eco_Has_Winner_In_Leg'].sum() / total_races * 100) if total_races else 0
    wide_leg_rate = (df['Wide_Has_Winner_In_Leg'].sum() / total_races * 100) if total_races else 0

    # Near Miss (1 Leg Miss)
    eco_1miss = (grouped['Eco_Miss_Count'] == 1).sum()
    wide_1miss = (grouped['Wide_Miss_Count'] == 1).sum()
    
    eco_1miss_rate = (eco_1miss / total_city_programs * 100) if total_city_programs else 0
    wide_1miss_rate = (wide_1miss / total_city_programs * 100) if total_city_programs else 0
    
    # Surprise Stats
    # Need to read Surprise columns from original dict if needed, but summary just asks for updates
    # Let's keep the existing surprise logic from previous run if possible, or recalculate
    # The previous report had: "Sürpriz Kazandı: 125". 
    # In daily_results: 'Surprise_Win' is 1 or 0
    surp_wins = df['Surprise_Win'].sum()
    surp_places = df['Surprise_Place'].sum()
    surp_count = df['Surprise_Candidate'].notna().sum()
    
    report = f"""
==================================================
           WALK-FORWARD BACKTEST RAPORU (V2)
==================================================
Tarih Aralığı  : {df['Date'].min()} - {df['Date'].max()}
Toplam Gün     : {total_days}
Toplam Program : {total_city_programs} (Şehir Bazlı)
Toplam Yarış   : {total_races}

--------------------------------------------------
🏆 BANKO PERFORMANSI
--------------------------------------------------
Toplam Banko   : {total_banko_assigned}
Banko Kazandı  : {total_banko_won}
Banko İlk 3    : {total_banko_top3}

>> KAZANMA ORANI : %{banko_win_rate:.2f}
>> İLK 3 ORANI   : %{banko_place_rate:.2f}

--------------------------------------------------
🎫 KUPON BAŞARISI (Ticket Pass - Tam İsabet)
--------------------------------------------------
Ekonomik Kupon : %{eco_ticket_rate:.2f} ({eco_tickets_won}/{total_city_programs})
Geniş Kupon    : %{wide_ticket_rate:.2f} ({wide_tickets_won}/{total_city_programs})

ORTALAMA TUTAN AYAK SAYISI:
- Eko   : {avg_eco_legs:.1f} / {avg_total_legs:.1f}
- Geniş : {avg_wide_legs:.1f} / {avg_total_legs:.1f}

1 AYAKLA YATAN (Direkten Dönen):
- Eko   : {eco_1miss} (%{eco_1miss_rate:.2f})
- Geniş : {wide_1miss} (%{wide_1miss_rate:.2f})

--------------------------------------------------
🐎 AYAK BAŞARISI (Leg Hit - Yarış Bazlı)
--------------------------------------------------
Eko Ayak Bulma : %{eco_leg_rate:.2f}
Geniş Ayak Bulma: %{wide_leg_rate:.2f}

--------------------------------------------------
⚠️ SÜRPRİZ MOTORU
--------------------------------------------------
İşaretlenen    : {surp_count}
Sürpriz Kazandı: {surp_wins}
Sürpriz Plase  : {surp_places}
==================================================
"""
    print(report)
    with open(SUMMARY_REPORT, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"✅ Saved Analysis to {SUMMARY_REPORT}")

if __name__ == "__main__":
    analyze()
