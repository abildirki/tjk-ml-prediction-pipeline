
from typing import List, Dict, Any

class ScoreCalibrator:
    def calibrate(self, predictions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # Group by race
        grouped = {}
        for p in predictions:
            key = (p['city'], p['race_no'])
            if key not in grouped: grouped[key] = []
            grouped[key].append(p)
            
        calibrated_predictions = []
        
        for key, runners in grouped.items():
            # Sort by score desc
            runners.sort(key=lambda x: x['base_score'], reverse=True)
            
            # Determine Score Range for Normalization
            min_score = min(r['base_score'] for r in runners)
            max_score = max(r['base_score'] for r in runners)
            score_range = max_score - min_score if max_score > min_score else 1.0

            N = len(runners)
            top1_pct = 0
            top2_pct = 0
            top3_pct = 0
            
            for rank_index, runner in enumerate(runners):
                # Calculate Score-based Percentile for true separation
                pct = (runner['base_score'] - min_score) / score_range
                
                runner['race_pct'] = round(pct, 3)
                runner['n_horses'] = N
                runner['rank_in_race'] = rank_index + 1
                
                if rank_index == 0: top1_pct = pct
                if rank_index == 1: top2_pct = pct
                if rank_index == 2: top3_pct = pct
                
            # Gap Calculation
            gap_pct = round(top1_pct - top2_pct, 3)
            gap_top1_top3 = round(top1_pct - top3_pct, 3)
            
            # Dynamic Threshold
            # Formula: 0.05 + (0.8 / N) (assuming 8/N was typo and meant 0.8 to be achievable)
            gap_threshold = 0.05 + (0.8 / N) if N > 0 else 0.0
            
            # Risk Heuristic
            is_risk_heuristic = (N >= 12 and gap_pct < 0.12)
            
            # Apply Labels
            for runner in runners:
                runner['race_gap_pct'] = gap_pct
                pct = runner['race_pct']
                
                # Determine Coupon Tags
                eco_cut = 3 if is_risk_heuristic else 2
                wide_cut = 5 if is_risk_heuristic else 4
                
                rank = runner['rank_in_race']
                coupon_tags = []
                if rank <= eco_cut: coupon_tags.append("EKO")
                if rank <= wide_cut: coupon_tags.append("GENIS")
                runner['coupon_tags'] = "+".join(coupon_tags)
                
                # Labeling
                label = "PLASE"
                
                # BANKO Logic
                # 1. race_pct >= 0.97 (Usually 1.0 for winner)
                # 2. race_gap_pct >= gap_threshold
                # 3. race_pct_top1 - race_pct_top3 >= 0.15
                is_banko = False
                if pct >= 0.97:
                    if gap_pct >= gap_threshold:
                        if gap_top1_top3 >= 0.15:
                            is_banko = True
                            
                if is_banko:
                    label = "BANKO"
                elif pct >= 0.90:
                    label = "GÜÇLÜ FAVORİ"
                
                # Surprise Logic
                # race_pct 0.60-0.88 + High Surprise Index
                s_idx = runner.get('surprise_score', 0)
                if 0.60 <= pct <= 0.88 and s_idx > 5.0:
                    label = "SÜRPRİZ ADAYI"
                    
                runner['calibrated_label'] = label
            
            calibrated_predictions.extend(runners)
            
        return calibrated_predictions
