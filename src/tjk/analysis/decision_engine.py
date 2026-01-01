
from datetime import date
from typing import Dict, List, Any
from sqlalchemy.orm import Session
from .profile import HorseProfile
from tjk.storage.schema import RaceModel

class DecisionEngine:
    def __init__(self, db_session: Session, profiles: Dict[str, HorseProfile]):
        self.db = db_session
        self.profiles = profiles
        
    def analyze_daily_program(self, target_date: date, cities: List[str]) -> List[Dict[str, Any]]:
        results = []
        
        # Fetch today's races
        races = self.db.query(RaceModel).filter(
            RaceModel.date == target_date,
            RaceModel.city.in_(cities)
        ).order_by(RaceModel.city, RaceModel.race_no).all()
        
        for race in races:
            race_res = self._analyze_race(race)
            results.extend(race_res)
            
        return results
        
    def _analyze_race(self, race: RaceModel) -> List[Dict[str, Any]]:
        candidates = []
        
        surface = "SENTETİK" if race.surface and "SENTETİK" in race.surface.upper() else \
                  ("ÇİM" if race.surface and "ÇİM" in race.surface.upper() else "KUM")
        
        dist_key = "SHORT" if race.distance_m < 1600 else ("LONG" if race.distance_m > 1900 else "MED")
        
        for entry in race.entries:
            profile = self.profiles.get(entry.horse_name)
            
            # --- SCORING LOGIC ---
            base_score = 0
            surprise_score = 0
            risk = "HIGH"
            
            if profile and profile.total_races > 0:
                # 1. Base Power (Win Rate + Place Rate)
                # Win Rate (0-100) * 1.5 -> Max 150
                base_score += profile.win_rate * 1.5  
                base_score += profile.place_rate * 0.5 
                
                # 2. Condition Match (Surface & Distance)
                s_stats = profile.surface_stats.get(surface, {})
                s_runs = s_stats.get("runs", 0)
                s_wins = s_stats.get("wins", 0)
                
                if s_runs > 0:
                    s_win_rate = (s_wins / s_runs) * 100
                    base_score += s_win_rate * 0.5 # Boost if good on this surface
                
                d_stats = profile.distance_stats.get(dist_key, {})
                d_runs = d_stats.get("runs", 0)
                d_wins = d_stats.get("wins", 0)
                
                if d_runs > 0:
                    d_win_rate = (d_wins / d_runs) * 100
                    base_score += d_win_rate * 0.3 # Boost if good on this distance
                
                # 3. Form (Last 5 Ranks)
                # 1st -> 15 pts, 2nd -> 10, 3rd -> 5
                for i, r in enumerate(profile.last_5_ranks):
                    weight = 1.0 - (i * 0.1) # Decay recentness
                    if r == 1: base_score += 15 * weight
                    elif r == 2: base_score += 10 * weight
                    elif r <= 4: base_score += 5 * weight
                    
                # 4. Surprise Potential
                surprise_score = profile.surprise_index
                
                # Risk Calculation
                if profile.win_rate > 30 and len(profile.last_5_ranks) >= 3:
                     risk = "LOW"
                elif profile.place_rate > 50:
                     risk = "MED"
                     
            else:
                # Unknown horse (First run?)
                base_score = 15 # Starter bonus
                risk = "UNKNOWN"
                
            candidates.append({
                "city": race.city,
                "race_no": race.race_no,
                "horse": entry.horse_name,
                "base_score": round(base_score, 1),
                "surprise_score": round(surprise_score, 1),
                "risk": risk,
                "profile_stats": f"{profile.wins}/{profile.total_races}" if profile else "0/0"
            })
            
        # Normalize/Sort
        candidates.sort(key=lambda x: x['base_score'], reverse=True)
        return candidates

