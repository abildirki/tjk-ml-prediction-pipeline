import pandas as pd
import glob
import json
import os

def generate_stability_report(sim_dir="outputs/sim"):
    print("📊 GENERATING STABILITY REPORT...")
    
    # 1. Load Daily Metrics
    json_files = glob.glob(f"{sim_dir}/daily/*_metrics.json")
    if not json_files:
        print("❌ No simulation data found.")
        return
        
    data = []
    for f in json_files:
        with open(f, 'r') as jf:
            m = json.load(jf)
            # Filename has date: YYYY-MM-DD_metrics.json
            base = os.path.basename(f)
            date_str = base.split('_metrics')[0]
            m['date'] = date_str
            data.append(m)
            
    df = pd.DataFrame(data)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date')
    
    # 2. Aggregations
    total_races = df['races'].sum()
    
    # Global Weighted Average
    global_hit1 = (df['hit_rate_top1'] * df['races']).sum() / total_races
    global_hit3 = (df['hit_rate_top3'] * df['races']).sum() / total_races
    
    # Rolling Stats (7-Day)
    df['rolling_hit1'] = df['hit_rate_top1'].rolling(7).mean()
    df['rolling_hit3'] = df['hit_rate_top3'].rolling(7).mean()
    
    # Worst Days (Hit@3 Low or High Surprises)
    # Define 'stability_score' = (hit3 * 100) - (missed_surprises * 5)
    df['sim_score'] = (df['hit_rate_top3'] * 100) - (df['surprise_winners_missed'] * 5)
    worst_days = df.nsmallest(10, 'sim_score')[
        ['date', 'races', 'hit_rate_top1', 'hit_rate_top3', 'surprise_winners_missed']
    ]
    
    # RISK LABEL BREAKDOWN AGGREGATION
    risk_stats = {} # {label: {count, hits1, hits3}}
    
    for record in data:
        daily_risk = record.get('risk_breakdown', {})
        for label, metrics in daily_risk.items():
            if label not in risk_stats:
                risk_stats[label] = {'count': 0, 'hits1': 0, 'hits3': 0}
            
            c = metrics['count']
            risk_stats[label]['count'] += c
            risk_stats[label]['hits1'] += metrics['hit1'] * c # Back to raw count
            risk_stats[label]['hits3'] += metrics['hit3'] * c
            
    # Convert to DataFrame
    risk_rows = []
    for lbl, s in risk_stats.items():
        if s['count'] > 0:
            risk_rows.append({
                "Label": lbl,
                "Races": s['count'],
                "Hit@1": s['hits1'] / s['count'],
                "Hit@3": s['hits3'] / s['count']
            })
    df_risk = pd.DataFrame(risk_rows).sort_values('Hit@1', ascending=False)

    # 3. Output JSON
    summary = {
        "period_start": str(df['date'].min().date()),
        "period_end": str(df['date'].max().date()),
        "total_days": len(df),
        "total_races": int(total_races),
        "global_hit_rate_1": global_hit1,
        "global_hit_rate_3": global_hit3,
        "worst_day_hit3": df['hit_rate_top3'].min(),
        "best_day_hit3": df['hit_rate_top3'].max(),
        "risk_breakdown": risk_stats
    }
    
    with open(f"{sim_dir}/stability_summary.json", "w") as f:
        json.dump(summary, f, indent=4)
        
    # 4. Simple MD Report
    report = f"""# Stability Report (Enhanced)
**Period**: {summary['period_start']} to {summary['period_end']}
**Total Races**: {summary['total_races']}

## Global Performance
- **Hit Rate @ 1**: {global_hit1:.1%}
- **Hit Rate @ 3**: {global_hit3:.1%}

## Risk Profile Analysis (AI Strategy Proof)
{df_risk.to_markdown(index=False, floatfmt=".1%")}

## Worst 10 Days (Stability Check)
Sorted by composite score (Hit@3 - Surprise Penalty)
{worst_days.to_markdown(index=False)}

## Rolling Trends (Last 7 Days)
{df.tail(7)[['date', 'hit_rate_top1', 'hit_rate_top3']].to_markdown(index=False)}
    """
    
    with open(f"{sim_dir}/stability_summary.json", "w") as f:
        json.dump(summary, f, indent=4)
        
    # 4. Simple MD Report
    report = f"""# Stability Report (Enhanced)
**Period**: {summary['period_start']} to {summary['period_end']}
**Total Races**: {summary['total_races']}

## Global Performance
- **Hit Rate @ 1**: {global_hit1:.1%}
- **Hit Rate @ 3**: {global_hit3:.1%}

## Worst 10 Days (Stability Check)
Sorted by composite score (Hit@3 - Surprise Penalty)
{worst_days.to_markdown(index=False)}

## Rolling Trends (Last 7 Days)
{df.tail(7)[['date', 'hit_rate_top1', 'hit_rate_top3']].to_markdown(index=False)}
    """
    
    with open(f"{sim_dir}/stability_report.md", "w", encoding='utf-8') as f:
        f.write(report)
        
    print(json.dumps(summary, indent=4))
    print(f"✅ Report saved to {sim_dir}/stability_report.md")

if __name__ == "__main__":
    generate_stability_report()
