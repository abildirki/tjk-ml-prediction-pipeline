import pandas as pd
import json
import os
from typing import Dict, Any

class TicketValidator:
    def __init__(self, ticket_dir="outputs/tickets", preds_dir="outputs/sim/daily"):
        self.ticket_dir = ticket_dir
        self.preds_dir = preds_dir
        
    def validate_ticket(self, date_str: str) -> Dict[str, Any]:
        """
        Validates a ticket against actual results.
        Returns detailed result dict.
        """
        ticket_path = f"{self.ticket_dir}/{date_str}_ticket.json"
        
        # Determine predictions path (Sim or Daily Report)
        sim_path = f"{self.preds_dir}/{date_str}_predictions.csv"
        # If not in sim/daily, maybe output/daily_reports?
        # But validator mostly used for simulation validation.
        csv_path = sim_path 
        if not os.path.exists(csv_path):
             csv_path = f"outputs/daily_reports/{date_str}.csv"
        
        if not os.path.exists(ticket_path):
            return {"error": f"Ticket not found: {ticket_path}"}
        if not os.path.exists(csv_path):
            return {"error": f"Results not found: {csv_path}"}
            
        # Load Data
        with open(ticket_path, 'r', encoding='utf-8') as f:
            ticket = json.load(f)
            
        df = pd.read_csv(csv_path)
        
        # Check if 'rank' or 'actual_rank' exists
        rank_col = 'rank'
        if rank_col not in df.columns:
            if 'actual_rank' in df.columns: rank_col = 'actual_rank'
            else: return {"error": "Prediction CSV has no 'rank' output. Cannot verify."}
            
        # Validation Loop
        results = {
            "date": date_str,
            "chaos_index": ticket['chaos_index'],
            "total_races": 0,
            "passed_legs": 0,
            "failed_legs": 0,
            "details": []
        }
        
        # Filter winners
        winners_df = df[df[rank_col] == 1]
        
        # Map winners by (city, race_no) -> Horse Name
        winner_map = {}
        for _, row in winners_df.iterrows():
            key = (row['city'], row['race_no'])
            winner_map[key] = {
                "horse": row['horse'],
                "ganyan": row.get('ganyan', 0),
                "rank": 1
            }
            
        for race in ticket['races']:
            city = race['city']
            r_no = race['race_no']
            key = (city, r_no)
            
            # Selected Horses
            selected_names = [h['horse_name'] for h in race['horses']]
            
            # Actual Winner
            actual = winner_map.get(key)
            
            status = "UNKNOWN"
            if actual:
                if actual['horse'] in selected_names:
                    status = "✅ PASS"
                    results['passed_legs'] += 1
                else:
                    status = "❌ FAIL"
                    results['failed_legs'] += 1
            else:
                status = "❓ NO DATA"
                
            results['total_races'] += 1
            results['details'].append({
                "city": city,
                "race": r_no,
                "label": race['risk_label'],
                "selected": selected_names,
                "winner": actual['horse'] if actual else "Unknown",
                "ganyan": actual['ganyan'] if actual else 0,
                "status": status
            })
            
        results['success_rate'] = results['passed_legs'] / results['total_races'] if results['total_races'] > 0 else 0
        
        return results

    def print_report(self, date_str):
        res = self.validate_ticket(date_str)
        if "error" in res:
            print(f"Error: {res['error']}")
            return
            
        print(f"\n📊 TICKET VALIDATION REPORT: {res['date']}")
        print(f"Chaos Index: {res['chaos_index']:.1%}")
        print(f"Success: {res['passed_legs']} / {res['total_races']} legs ({res['success_rate']:.1%})")
        print("-" * 60)
        print(f"{'WC':<15} {'Race':<5} {'Risk':<10} {'Status':<10} {'Winner (Ganyan)':<20} {'Your Picks'}")
        print("-" * 60)
        
        for d in res['details']:
            shorts = [n[:10] for n in d['selected']]
            picks_str = ", ".join(shorts)
            winner_str = f"{d['winner'][:15]} ({d['ganyan']})"
            print(f"{d['city']:<15} {d['race']:<5} {d['label']:<10} {d['status']:<10} {winner_str:<20} {picks_str}")
            
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        TicketValidator().print_report(sys.argv[1])
    else:
        print("Usage: python -m tjk.ticket.validator YYYY-MM-DD")
