from typing import List, Dict, Any
import pandas as pd

def generate_rationale(row: pd.Series) -> List[str]:
    """
    Generates evidence-based rationales for a horse selection.
    Uses only available columns in the row to avoid hallucinations.
    """
    bullets = []
    
    # 1. Model Confidence
    score = row.get('final_score_dynamic', row.get('final_score', 0.0))
    if score > 0.7:
        bullets.append(f"🤖 **Yüksek AI Skoru**: {score:.2f} (Çok Güçlü)")
    elif score > 0.5:
        bullets.append(f"🤖 **İyi AI Skoru**: {score:.2f}")

    # 2. Recent Form (Last 5)
    # Assuming columns like 'avg_rank_last5', 'win_rate_last5' exist (from feature builder)
    # Check if they exist explicitly or derived
    if 'win_rate_last5' in row and row['win_rate_last5'] > 0.3:
        bullets.append(f"🔥 **Formda**: Son 5 yarışta kazanma oranı: %{row['win_rate_last5']*100:.0f}")
    
    if 'avg_rank_last5' in row and row['avg_rank_last5'] <= 2.5:
        bullets.append(f"⭐ **İstikrar**: Son 5 yarış ortalama sıralaması: {row['avg_rank_last5']:.1f}")

    # 3. Specialization (Track/Dist)
    # 'track_specialization_ratio' > 1.0 means better than their average
    if 'track_specialization_ratio' in row and row['track_specialization_ratio'] > 1.2:
        bullets.append(f"🏟️ **Pist Uzmanı**: Bu pistte genel performansından %{ (row['track_specialization_ratio']-1)*100:.0f } daha iyi.")

    if 'dist_specialization_ratio' in row and row['dist_specialization_ratio'] > 1.2:
        bullets.append(f"🏃 **Mesafe Uzmanı**: Bu mesafeyi seviyor (Ratio: {row['dist_specialization_ratio']:.2f}).")
        
    # 4. Same Track Win Rate (Direct evidence)
    if 'same_track_win_rate' in row and row['same_track_win_rate'] > 0.4:
         bullets.append(f"🏆 **Pist Galibi**: Bu pistte kazanma oranı %{row['same_track_win_rate']*100:.0f}.")

    # 5. Jockey/Horse Synergy (If available)
    # (Columns might not be strictly standardized in 'prediction' output unless joined, 
    # but let's check for standard feature names)
    
    # 6. SP Reason (If explicitly provided via analysis)
    if 'sp_reason' in row and pd.notna(row['sp_reason']):
        bullets.append(f"🕵️ **Sürpriz Nedeni**: {row['sp_reason']}")
        
    # 7. Win Prob vs AGF (Value Bet)
    win_prob = row.get('model_win', 0)
    agf = row.get('agf', 100) # Default high to avoid trigger
    # If model thinks 30% win chance but AGF is 5% (20.0 odds approx logic, but AGF is %)
    # AGF is usually % distribution.
    if win_prob > 0.30 and agf < 10:
         bullets.append(f"💎 **Değerli Bahis**: Model kazanma şansını %{win_prob*100:.0f} görüyor ama AGF sadece %{agf:.1f}.")

    # Fallback
    if not bullets:
        bullets.append("Genel model tercihi.")

    return bullets[:5] # Max 5 items
