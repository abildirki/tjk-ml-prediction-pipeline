from datetime import date
from typing import List, Optional
from .base import TJKBaseModel
from .enums import Gender

class PastPerformance(TJKBaseModel):
    horse_id: str
    date: date
    city: str
    surface: str
    distance_m: int
    finish_pos: int
    time_sec: Optional[float] = None
    weight_kg: float
    jockey_name: str

class HorseProfile(TJKBaseModel):
    horse_id: str
    name: str
    gender: Gender = Gender.UNKNOWN
    age: Optional[int] = None
    sire: Optional[str] = None
    dam: Optional[str] = None
    birth_year: Optional[int] = None
    history: List[PastPerformance] = []
