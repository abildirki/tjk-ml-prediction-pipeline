from datetime import date, time
from typing import List, Optional
from pydantic import Field
from .base import TJKBaseModel
from .enums import SurfaceType

class Entry(TJKBaseModel):
    race_id: str
    horse_id: str
    horse_name: str
    saddle_no: Optional[int] = None
    jockey_id: Optional[str] = None
    jockey_name: Optional[str] = None
    weight_kg: Optional[float] = None
    trainer_id: Optional[str] = None
    owner_id: Optional[str] = None
    hp: Optional[int] = None
    kgs: Optional[int] = None
    s20: Optional[int] = None
    agf: Optional[float] = None
    form_score: Optional[str] = None # "63KS2" form record
    
    # Results
    rank: Optional[int] = None
    finish_time: Optional[str] = None
    ganyan: Optional[str] = None
    equipment: Optional[str] = None
    
class Race(TJKBaseModel):
    race_id: str
    date: date
    city: str
    race_no: int
    time: Optional[time] = None
    surface: SurfaceType = SurfaceType.UNKNOWN
    distance_m: int
    category: Optional[str] = None
    prize_1st: Optional[float] = None
    entries: List[Entry] = Field(default_factory=list)
