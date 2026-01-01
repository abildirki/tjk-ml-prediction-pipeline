import pandas as pd
import os

DAILY_CSV = "outputs/backtest/daily_results.csv"
OUTPUT_DIR = "outputs/backtest"

def analyze_six_ganyan():
    if not os.path.exists(DAILY_CSV):
        print(f"❌ File not found: {DAILY_CSV}")
        return

    print("🚀 Starting Six Ganyan Analysis...")
    df = pd.read_csv(DAILY_CSV)
    
    # Ensure columns exist (handle case where rename might not have persisted if separate run)
    # The previous step did overwrite, so we assume new names.
    # Just in case, normalized check:
    if 'Is_Scientific_Winner_In_Eco' in df.columns:
        df.rename(columns={
            'Is_Scientific_Winner_In_Eco': 'Eco_Has_Winner_In_Leg',
            'Is_Scientific_Winner_In_Wide': 'Wide_Has_Winner_In_Leg'
        }, inplace=True)

    # Convert Race to int just in case
    df['Race'] = df['Race'].astype(int)

    # Group by Program (Date + City)
    programs = df.groupby(['Date', 'City'])
    
    # Scenarios: Start Race 1, 2, 3
    scenarios = [1, 2, 3]
    
    overall_report = []

    for start_race in scenarios:
        print(f"\n🔄 Processing Senaryo: Start Race {start_race}...")
        
        scenario_results = []
        
        for (date, city), group in programs:
            # Sort by Race
            group = group.sort_values('Race')
            
            # Select 6 races starting from start_race
            # We look for Race Numbers: start_race, start_race+1, ..., start_race+5
            target_races = range(start_race, start_race + 6)
            
            # Filter specifically for these race numbers
            ticket_slice = group[group['Race'].isin(target_races)]
            
            # Check completeness
            # Must have exactly 6 races found.
            if len(ticket_slice) != 6:
                # Filter out incomplete days (e.g. maybe that city only had 5 races, or we started at 3 and it only went to 7 (5 races))
                continue
                
            # Verify they are contiguous? the isin check + length 6 guarantees we found 6 distinct race numbers in that range.
            
            # Calculate Metrics for this Ticket
            eco_hits = ticket_slice['Eco_Has_Winner_In_Leg'].sum()
            wide_hits = ticket_slice['Wide_Has_Winner_In_Leg'].sum()
            
            banko_df = ticket_slice[ticket_slice['Banko_Horse'].notna()]
            banko_total = len(banko_df)
            banko_wins = banko_df['Banko_Win'].sum()
            
            surp_wins = ticket_slice['Surprise_Win'].sum()
            
            row = {
                'Date': date,
                'City': city,
                'Start_Race': start_race,
                'End_Race': start_race + 5,
                'Eco_Legs_Hit': eco_hits,
                'Wide_Legs_Hit': wide_hits,
                'Eco_Ticket_Pass': 1 if eco_hits == 6 else 0,
                'Wide_Ticket_Pass': 1 if wide_hits == 6 else 0,
                'Eco_Miss_Count': 6 - eco_hits,
                'Wide_Miss_Count': 6 - wide_hits,
                'Banko_Count': banko_total,
                'Banko_Wins': banko_wins,
                'Surprise_Wins': surp_wins
            }
            scenario_results.append(row)
            
        # Analysis for this Scenario
        res_df = pd.DataFrame(scenario_results)
        
        if res_df.empty:
            print(f"   ⚠️ No valid 6-race tickets found for starting race {start_race}")
            continue
            
        # Save CSV
        csv_path = f"{OUTPUT_DIR}/sixli_start_{start_race}_summary.csv"
        res_df.to_csv(csv_path, index=False)
        
        # Stats
        total_tickets = len(res_df)
        
        eco_pass = res_df['Eco_Ticket_Pass'].sum()
        wide_pass = res_df['Wide_Ticket_Pass'].sum()
        
        avg_eco_legs = res_df['Eco_Legs_Hit'].mean()
        avg_wide_legs = res_df['Wide_Legs_Hit'].mean()
        
        eco_1miss = (res_df['Eco_Miss_Count'] == 1).sum()
        wide_1miss = (res_df['Wide_Miss_Count'] == 1).sum()
        
        # Report String
        report_text = f"""
==================================================
   6'LI GANYAN SENARYO ANALİZİ (Giriş: {start_race}. Koşu)
==================================================
Toplam Kupon    : {total_tickets}

--------------------------------------------------
🎫 EKONOMİK KUPON
--------------------------------------------------
Tam İsabet (6/6): {eco_pass} (%{eco_pass/total_tickets*100:.2f})
Ortalama Ayak   : {avg_eco_legs:.2f} / 6.00
1 Ayakla Yatan  : {eco_1miss} (%{eco_1miss/total_tickets*100:.2f})

--------------------------------------------------
🎫 GENİŞ KUPON
--------------------------------------------------
Tam İsabet (6/6): {wide_pass} (%{wide_pass/total_tickets*100:.2f})
Ortalama Ayak   : {avg_wide_legs:.2f} / 6.00
1 Ayakla Yatan  : {wide_1miss} (%{wide_1miss/total_tickets*100:.2f})

--------------------------------------------------
🏆 BANKO & SÜRPRİZ
--------------------------------------------------
Toplam Banko    : {res_df['Banko_Count'].sum()} (Ort {res_df['Banko_Count'].mean():.1f} / kupon)
Banko Başarısı  : %{(res_df['Banko_Wins'].sum() / res_df['Banko_Count'].sum() * 100) if res_df['Banko_Count'].sum() else 0:.2f}
Toplam Sürpriz  : {res_df['Surprise_Wins'].sum()} (Kuponlardaki kazanan sürprizler)
==================================================
"""
        # Save Report
        txt_path = f"{OUTPUT_DIR}/sixli_start_{start_race}_overall.txt"
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(report_text)
            
        print(report_text)
        overall_report.append(report_text)

    # Save Combined
    with open(f"{OUTPUT_DIR}/sixli_consolidated_report.txt", 'w', encoding='utf-8') as f:
        f.write("\n".join(overall_report))
        
    print(f"✅ Six Ganyan Analysis Completed. Files saved to {OUTPUT_DIR}")

if __name__ == "__main__":
    analyze_six_ganyan()
