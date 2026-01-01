
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import date

@dataclass
class HorseProfile:
    horse_name: str
    
    # Global Stats
    total_races: int = 0
    wins: int = 0
    places: int = 0 # Top 4
    
    # Context Stats
    surface_stats: Dict[str, Dict[str, int]] = field(default_factory=lambda: {
        "KUM": {"runs": 0, "wins": 0, "places": 0},
        "ÇİM": {"runs": 0, "wins": 0, "places": 0},
        "SENTETİK": {"runs": 0, "wins": 0, "places": 0}
    })
    
    distance_stats: Dict[str, Dict[str, int]] = field(default_factory=lambda: {
        "SHORT": {"runs": 0, "wins": 0, "places": 0}, # < 1600
        "MED": {"runs": 0, "wins": 0, "places": 0},   # 1600 - 1900
        "LONG": {"runs": 0, "wins": 0, "places": 0}    # > 1900
    })
    
    city_stats: Dict[str, Dict[str, int]] = field(default_factory=dict)

    # Advanced Metrics
    surprise_index: float = 0.0  # Accumulates when winning with low AGF
    last_5_ranks: List[int] = field(default_factory=list)
    
    # Decay factor for old "Surprise" points
    last_race_date: Optional[date] = None

    def update(self, race_date: date, race_city: str, surface: str, distance: int, 
               rank: Optional[int], agf: Optional[float], jockey: str):
        
        self.total_races += 1
        self.last_race_date = race_date
        
        # Rank-based updates
        is_win = (rank == 1)
        is_place = (rank is not None and rank <= 4)
        
        if is_win: self.wins += 1
        if is_place: self.places += 1
        
        # Surface Stats
        s_key = "SENTETİK" if surface and "SENTETİK" in surface.upper() else \
                ("ÇİM" if surface and "ÇİM" in surface.upper() else "KUM")
        
        if s_key not in self.surface_stats:
            self.surface_stats[s_key] = {"runs": 0, "wins": 0, "places": 0}
            
        self.surface_stats[s_key]["runs"] += 1
        if is_win: self.surface_stats[s_key]["wins"] += 1
        if is_place: self.surface_stats[s_key]["places"] += 1
        
        # Distance Stats
        d_key = "SHORT" if distance < 1600 else ("LONG" if distance > 1900 else "MED")
        self.distance_stats[d_key]["runs"] += 1
        if is_win: self.distance_stats[d_key]["wins"] += 1
        if is_place: self.distance_stats[d_key]["places"] += 1

        # City Stats
        c_key = race_city.upper()
        if c_key not in self.city_stats:
            self.city_stats[c_key] = {"runs": 0, "wins": 0, "places": 0}
        self.city_stats[c_key]["runs"] += 1
        if is_win: self.city_stats[c_key]["wins"] += 1
        if is_place: self.city_stats[c_key]["places"] += 1
        
        # Form
        if rank:
            self.last_5_ranks.insert(0, rank)
            self.last_5_ranks = self.last_5_ranks[:5]
            
        # Surprise Index
        # Trigger: Win with AGF < 5.0 (approx < 20% prob) OR Place with AGF < 2.0
        # Wait, AGF usually 1-30. Low AGF = Low chance? No, AGF is %, High is good.
        # So "Surprise" is winning with LOW AGF (e.g. < 5%).
        # Or High Odds (Ganyan). Since we have AGF more reliably:
        # If AGF is present:
        if agf is not None:
            # Surprise Win: Won with < 10% AGF
            if is_win and agf < 10.0:
                surge = (15.0 - agf) # e.g. 2% AGF -> 13 pts. 9% AGF -> 6 pts.
                self.surprise_index += surge
            
            # Surprise Place: Place with < 3% AGF
            elif is_place and agf < 3.0:
                self.surprise_index += 3.0
        
        # Decay Surprise Index slightly every race to prioritize recent surprises
        self.surprise_index *= 0.95 

    @property
    def win_rate(self) -> float:
        return (self.wins / self.total_races) * 100 if self.total_races > 0 else 0.0
        
    @property
    def place_rate(self) -> float:
        return (self.places / self.total_races) * 100 if self.total_races > 0 else 0.0

