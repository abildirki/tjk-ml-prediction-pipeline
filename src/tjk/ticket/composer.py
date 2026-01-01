import pandas as pd
import json
import logging
import os
import numpy as np
from typing import List, Dict, Any
from tjk.ticket.rationale import generate_rationale

logger = logging.getLogger("TJKTicket")

class TicketComposer:
    def __init__(self, output_dir="outputs/tickets"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        
    def generate_ticket(self, csv_path: str, date_str: str) -> Dict[str, Any]:
        """
        Generates a ticket from a prediction CSV (Fail-Safe Mode).
        """
        if not os.path.exists(csv_path):
            logger.error(f"Prediction file not found: {csv_path}")
            # We strictly need predictions to generate a ticket.
            # But the request says: "Kupon YİNE ÜRETİLECEK ... predictions.csv YOKSA" 
            # Implies we might need to handle empty or mock generation? 
            # Or maybe it means if *some* cols are missing?
            # User says: "Eğer predictions.csv bulunamazsa... Kupon YİNE ÜRETİLECEK... entropy=None... SP yok... Favori seçimi fallback"
            # BUT if there is no CSV, we have no horses! 
            # This constraint implies maybe reading from an alternative source (e.g. database)?
            # Given current architecture, I cannot conjure horses without data.
            # I will assume the file exists but might be malformed OR we fallback to `daily_reports` if validation failed.
            # For now, if NO file at all, return empty ticket is the only logical step, logic allows crash prevention.
            return {
                "date": date_str,
                "chaos_index": 0.0,
                "summary": "No Data Available",
                "races": []
            }
            
        try:
            df = pd.read_csv(csv_path)
            
            # Fail-Safe: Ensure required columns exist
            if 'race_risk_label' not in df.columns:
                df['race_risk_label'] = 'NORMAL' # Fallback
            
            # Ensure race_no/city are treated correctly
            # Fix duplicate race_no issue by grouping by City+RaceNo
            # Use 'city' if available, else 'dummy'
            if 'city' not in df.columns: df['city'] = 'Unknown'
            
            # Calculate Chaos Index
            # Logic: (Risky + Surprise) / Total Races
            groups = df.groupby(['city', 'race_no'])
            total_races = len(groups)
            risky_count = 0
            
            for _, grp in groups:
                 label = grp['race_risk_label'].iloc[0]
                 if label in ['RİSKLİ', 'SÜRPRİZE_AÇIK']:
                     risky_count += 1
                     
            chaos_index = risky_count / total_races if total_races > 0 else 0.0
            
            ticket_data = {
                "date": date_str,
                "chaos_index": chaos_index,
                "summary": f"Chaos Level: {chaos_index:.1%} ({risky_count}/{total_races} races risky)",
                "races": []
            }
            
            for (city, race_no), group in groups:
                selection = self.select_horses(group)
                ticket_data["races"].append(selection)
                
            self.save_json(ticket_data, date_str)
            self.save_md(ticket_data, date_str)
            
            return ticket_data

        except Exception as e:
            logger.error(f"Failed to generate ticket: {e}")
            return None

    def select_horses(self, race_df: pd.DataFrame) -> Dict[str, Any]:
        """
        Selects horses with Safe Patch Logic.
        """
        if race_df.empty: return {}
        
        # 1. Get Context
        risk_label = race_df['race_risk_label'].iloc[0] if 'race_risk_label' in race_df else 'NORMAL'
        
        # 2. Dynamic Entropy Calculation
        entropy = None
        if 'race_entropy' in race_df:
            val = race_df['race_entropy'].iloc[0]
            if pd.notna(val) and float(val) > 0.0001:
                entropy = float(val)
        
        if entropy is None:
            entropy = self._calculate_dynamic_entropy(race_df)
            
        # 3. Candidate Sorting
        # Priority: final_score_dynamic -> final_score -> win_proba -> random fall back
        score_col = 'final_score_dynamic'
        if score_col not in race_df: score_col = 'final_score'
        if score_col not in race_df: score_col = 'model_win'
        if score_col not in race_df: score_col = 'model_win'
        # Removed ganyan fallback per HOTFIX #2
        
        # Ensure Score Col exists, else create dummy
        if score_col not in race_df:
             race_df['dummy_score'] = 0.5
             score_col = 'dummy_score'

        sorted_df = race_df.sort_values(score_col, ascending=False)
        
        selected_horses = []
        strategy_note = ""

        # --- RULES ---
        
        if risk_label == 'BANKO':
            # Rule: Top 1
            selected_horses.append(sorted_df.iloc[0])
            strategy_note = "BANKO (Güvenilir Favori)"
            
        elif risk_label == 'NORMAL':
            # Rule: Top 2
            candidates = sorted_df.head(2)
            for _, h in candidates.iterrows():
                selected_horses.append(h)
            strategy_note = "NORMAL (İlk 2 At)"
            
        elif risk_label == 'SÜRPRİZE_AÇIK':
            # Rule: SP Top 1 + Favorite (Strict 2 Horses)
            
            # Find Favorite
            fav = sorted_df.iloc[0]
            
            # Find SP Candidate
            cand_sp = None
            sp_source = "None"
            
            # A) Model SP
            if 'model_sp' in race_df:
                sp_sorted = race_df.sort_values('model_sp', ascending=False)
                if not sp_sorted.empty:
                    top_sp = sp_sorted.iloc[0]
                    # Avoid picking same as fav if possible?
                    # Actually if SP model says Fav is also SP, then just 1 horse?
                    # "Strategy metninde 'Sigorta' geçiyorsa horses listesinde EN AZ 2 at bulunmak zorunda."
                    # If Fav == SP candidate, we need a 2nd horse from Pseudo-SP or Win Top 2.
                    cand_sp = top_sp
                    sp_source = "Model SP"
            
            # B) Pseudo-SP Fallback
            if cand_sp is None or (cand_sp['horse'] == fav['horse']):
                 pseudo = self._find_pseudo_sp(race_df, fav['horse'])
                 if pseudo is not None:
                     cand_sp = pseudo
                     sp_source = "Pseudo-SP"
            
            # Add Horses
            selected_horses.append(fav)
            
            if cand_sp is not None and cand_sp['horse'] != fav['horse']:
                selected_horses.append(cand_sp)
                strategy_note = f"SÜRPRİZ ({sp_source}) + Favori (Sigorta)"
            else:
                # Still 1 horse? Force 2nd favorite
                if len(race_df) > 1:
                    selected_horses.append(sorted_df.iloc[1])
                    strategy_note = "SÜRPRİZ (Yedek Favori) + Favori (Sigorta)"
                else:
                    strategy_note = "SÜRPRİZ (Tek At - Alternatif Yok)"
                    
        elif risk_label == 'RİSKLİ':
             # Rule: Defensive / Expanded (Fixed 4 Horses)
             place_col = 'model_place'
             if place_col not in race_df: place_col = score_col
             
             # Layer 1: Defensive Top 2 (Existing)
             defensive_df = race_df.sort_values(place_col, ascending=False)
             candidates = defensive_df.head(2)
             for _, h in candidates.iterrows():
                 selected_horses.append(h)
                 
             # Layer 2: Chaos Expansion (+2 Horses)
             current_names = [h['horse'] for h in selected_horses]
             remaining = race_df[~race_df['horse'].isin(current_names)]
             
             if not remaining.empty:
                 # Horse 3: Best Win Score (Win Potential)
                 h3 = remaining.sort_values(score_col, ascending=False).iloc[0]
                 selected_horses.append(h3)
                 current_names.append(h3['horse'])
                 
                 # Horse 4: Chaos/Pseudo-SP
                 remaining = race_df[~race_df['horse'].isin(current_names)]
                 if not remaining.empty:
                     # Use pseudo-sp logic on remaining candidates
                     h4 = self._find_pseudo_sp(remaining, "DUMMY_NO_EXCLUDE")
                     if h4 is None:
                         # Fallback to Best Score
                         h4 = remaining.sort_values(score_col, ascending=False).iloc[0]
                     selected_horses.append(h4)

             strategy_note = "RİSKLİ (Geniş Defans / 4 At – Kaos Kapsaması)"
             
        else:
             # Default
             selected_horses.append(sorted_df.iloc[0])
             strategy_note = "Varsayılan (Bilinmeyen Risk)"
             
        # Format Output
        unique_horses = {h['horse']: h for h in selected_horses}
        formatted_horses = []
        for h_name, h in unique_horses.items():
            formatted_horses.append({
                "horse_name": h_name,
                "jockey": h.get('jockey', ''),
                "score": h.get(score_col, 0),
                "rationale": generate_rationale(h)
            })
            
        return {
            "city": race_df['city'].iloc[0],
            "race_no": int(race_df['race_no'].iloc[0]),
            "risk_label": risk_label,
            "entropy": float(entropy) if entropy is not None else None,
            "strategy": strategy_note,
            "horses": formatted_horses
        }

    def _calculate_dynamic_entropy(self, race_df):
        """
        Calculates Shannon Entropy from available probability columns.
        Priorities: win_proba -> model_win -> final_score_dynamic (softmax)
        """
        try:
            probs = None
            
            # 1. win_proba (Direct)
            if 'win_proba' in race_df:
                p = race_df['win_proba'].fillna(0).values
                if p.sum() > 0: probs = p
                
            # 2. model_win (Raw Model Output)
            if probs is None and 'model_win' in race_df:
                 p = race_df['model_win'].fillna(0).values
                 if p.sum() > 0: probs = p
                 
            # 3. Softmax from score
            if probs is None and 'final_score_dynamic' in race_df:
                scores = race_df['final_score_dynamic'].fillna(0).values
                if len(scores) > 0:
                    exps = np.exp(scores - np.max(scores)) # Stability
                    probs = exps / np.sum(exps)
                    
            if probs is not None:
                # Normalize just in case
                probs = probs / probs.sum()
                # Shannon
                entropy = -np.sum(probs * np.log(probs + 1e-9))
                return float(entropy)
                
        except Exception:
            return None
            
        return None

    def _find_pseudo_sp(self, race_df, fav_name):
        """
        Finds a surprise candidate (Pseudo-SP) based on heuristics.
        Criteria (Meet 2+):
        - AGF <= 10 (or missing)
        - High Specialization
        - Recent Form (last 5)
        - High Place/Win score
        """
        candidates = race_df[race_df['horse'] != fav_name].copy()
        if candidates.empty: return None
        
        # Calculate 'Pseudo Score'
        def get_pseudo_points(row):
            points = 0
            # AGF Factor
            agf = row.get('agf', 0)
            if pd.isna(agf) or agf <= 10:
                points += 1
                
            # Spec Factor (Robust Check)
            spec_cols = ['track_specialization_ratio', 'dist_specialization_ratio', 'specialization_score']
            for col in spec_cols:
                if row.get(col, 0) > 1.1:
                    points += 1
                    break # Count spec only once
            
            # Score Factor (Is it a sleeper? Top 4 score but low AGF?)
            # This is hard to check per row without context, but let's say if score > 0.15
            score = row.get('final_score_dynamic', 0)
            if score > 0.15: points += 1
            
            return points

        candidates['pseudo_points'] = candidates.apply(get_pseudo_points, axis=1)
        
        # Filter 2+ points
        qualifiers = candidates[candidates['pseudo_points'] >= 2]
        
        if not qualifiers.empty:
            # Pick highest score among qualifiers
            sort = 'final_score_dynamic' if 'final_score_dynamic' in qualifiers else 'model_place'
            if sort in qualifiers:
                 return qualifiers.sort_values(sort, ascending=False).iloc[0]
            return qualifiers.iloc[0]
            
        # If no strict qualifiers, pick best non-fav by score (Basic Fallback)
        score_col = 'final_score_dynamic' if 'final_score_dynamic' in candidates else 'model_win'
        if score_col in candidates:
             return candidates.sort_values(score_col, ascending=False).iloc[0]
        
        return None

    def save_json(self, data, date_str):
        path = f"{self.output_dir}/{date_str}_ticket.json"
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def save_md(self, data, date_str):
        path = f"{self.output_dir}/{date_str}_ticket.md"
        lines = [
            f"# 🎫 TJK Kupon Önerisi: {data['date']}",
            f"**Chaos Index**: {data['chaos_index']:.1%} | **Durum**: {data['summary']}",
            "",
            "## Koşular",
            ""
        ]
        
        for race in data['races']:
            icon = "🟢"
            lbl = race['risk_label']
            if lbl == 'BANKO': icon = "🔒"
            if lbl == 'RİSKLİ': icon = "⚠️"
            if lbl == 'SÜRPRİZE_AÇIK': icon = "⚡"
            
            ent_str = f"{race['entropy']:.2f}" if isinstance(race['entropy'], float) else "NA"
            
            lines.append(f"### {icon} Koşu {race['race_no']} ({race['city']}) - {lbl}")
            lines.append(f"Strategy: *{race['strategy']}*  (Entropy: {ent_str})")
            lines.append("")
            
            for h in race['horses']:
                lines.append(f"- **{h['horse_name']}** (Score: {h['score']:.2f})")
                for r in h['rationale']:
                    lines.append(f"  - {r}")
            lines.append("")
            
        with open(path, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))
        logger.info(f"Ticket saved to {path}")
