from typing import Dict, TypedDict

class Weights(TypedDict):
    win: float
    place: float
    sp: float

# Configuration for Dynamic Weights
# Centralized thresholds and values to avoid magic numbers.
WEIGHT_CONFIG = {
    "LONG_TURF": {
        "dist_min": 1700,
        "surface": "Çim", 
        "weights": {"win": 0.55, "place": 0.20, "sp": 0.25}
    },
    "SHORT_DIRT": {
        "dist_max": 1400, # Strictly less than
        "surface": "Kum",
        "weights": {"win": 0.75, "place": 0.15, "sp": 0.10}
    },
    "DEFAULT": {
        "weights": {"win": 0.65, "place": 0.20, "sp": 0.15}
    }
}

def get_dynamic_weights(surface: str, distance: float) -> Weights:
    """
    Determines model weights based on race context.
    
    Args:
        surface: Track surface (e.g., 'Çim', 'Kum', 'Sentetik')
        distance: Race distance in meters
        
    Returns:
        Dict with 'win', 'place', 'sp' weights.
    """
    # Rule 1: Long Distance Turf -> High Uncertainty -> More SP Weight
    # DNA Analysis showed SP winners favor Long Turf.
    cfg = WEIGHT_CONFIG["LONG_TURF"]
    if surface == cfg["surface"] and distance >= cfg["dist_min"]:
        return cfg["weights"]
        
    # Rule 2: Short Distance Dirt -> High Predictability -> More Win Weight
    # Sprint races on dirt are often dominated by speed favorites.
    cfg = WEIGHT_CONFIG["SHORT_DIRT"]
    if surface == cfg["surface"] and distance < cfg["dist_max"]:
        return cfg["weights"]
        
    # Default Strategy
    return WEIGHT_CONFIG["DEFAULT"]["weights"]

def calculate_dynamic_score(
    prob_win: float, 
    prob_place: float, 
    prob_sp: float, 
    surface: str, 
    distance: float
) -> tuple[float, Weights]:
    """
    Calculates the final score using context-aware weights.
    
    Returns:
        (final_score, weights_used)
    """
    w = get_dynamic_weights(str(surface), float(distance))
    
    score = (
        w["win"] * prob_win +
        w["place"] * prob_place +
        w["sp"] * prob_sp
    )
    
    return score, w
