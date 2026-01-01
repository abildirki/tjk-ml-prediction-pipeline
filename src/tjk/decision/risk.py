import numpy as np
import pandas as pd
from typing import Dict, Any

# Configuration for Risk Assessment
RISK_CONFIG = {
    "ENTROPY_LOW": 1.5,      # Clear favorite / few contenders
    "ENTROPY_HIGH": 2.2,     # Chaos
    "GAP_HIGH": 0.25,        # Strong favorite (>25% lead)
    "GAP_LOW": 0.05,         # Photo finish territory (<5% lead)
    "LABELS": {
        "BANKO": "BANKO",
        "RISKLI": "RİSKLİ",
        "SURPRISE": "SÜRPRİZE_AÇIK",
        "NORMAL": "NORMAL"
    }
}

def calculate_entropy(probs: np.array) -> float:
    """
    Calculates Shannon Entropy of the win probability distribution.
    Higher entropy = Higher uncertainty.
    """
    # Normalize just in case (though probs should strictly sum to 1 in theory, 
    # model outputs might sum >1 or <1, usually softmax ensures 1 but we use independent classifiers)
    # Our 'model_win' are probabilities from binary classifiers, so they don't sum to 1.
    # We must normalize them to treat as a distribution for entropy.
    
    prob_sum = np.sum(probs)
    if prob_sum == 0:
        return 0.0
        
    p_norm = probs / prob_sum
    
    # Filter zeros to avoid log(0)
    p_norm = p_norm[p_norm > 0]
    
    entropy = -np.sum(p_norm * np.log(p_norm))
    return float(entropy)

def classify_race_risk(df_race: pd.DataFrame, win_col: str = 'model_win') -> Dict[str, Any]:
    """
    Analyzes a single race to determine its risk profile.
    
    Args:
        df_race: DataFrame containing all horses in ONE race.
        win_col: Column name for win probability.
        
    Returns:
        Dict with entropy, gap, label.
    """
    probs = df_race[win_col].values
    
    # 1. Entropy
    entropy = calculate_entropy(probs)
    
    # 2. Gap (Top 1 vs Top 2)
    sorted_probs = np.sort(probs)[::-1] # Descending
    gap = 0.0
    if len(sorted_probs) >= 2:
        gap = sorted_probs[0] - sorted_probs[1]
    elif len(sorted_probs) == 1:
        gap = 1.0 # 1 horse race?
        
    # 3. Classification Rule
    # BANKO: Low Entropy (Order) AND High Gap (Dominant Horse)
    if entropy < RISK_CONFIG["ENTROPY_LOW"] and gap > RISK_CONFIG["GAP_HIGH"]:
        label = RISK_CONFIG["LABELS"]["BANKO"]
        
    # RISKY: High Entropy (Chaos) AND Low Gap (No leader)
    elif entropy > RISK_CONFIG["ENTROPY_HIGH"] and gap < RISK_CONFIG["GAP_LOW"]:
        label = RISK_CONFIG["LABELS"]["RISKLI"]
        
    # SURPRISE OPEN: Middle ground or specific logic
    # For now, let's use Entropy as main driver for 'Surprise Open'
    elif entropy > RISK_CONFIG["ENTROPY_HIGH"]:
        label = RISK_CONFIG["LABELS"]["SURPRISE"]
        
    else:
        label = RISK_CONFIG["LABELS"]["NORMAL"]
        
    return {
        "race_entropy": entropy,
        "top1_top2_gap": gap,
        "race_risk_label": label
    }
