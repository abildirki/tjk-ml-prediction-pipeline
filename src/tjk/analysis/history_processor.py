
from datetime import date
from typing import Dict
from sqlalchemy import text
from sqlalchemy.orm import Session, joinedload
from .profile import HorseProfile
from tjk.storage.schema import RaceModel, EntryModel

class HistoryProcessor:
    def __init__(self, db_session: Session):
        self.db = db_session
        self.profiles: Dict[str, HorseProfile] = {}
        
    def build_profiles(self, start_date: date = date(2025, 5, 5), end_date: date = None):
        print(f"Building profiles from history (Starting {start_date} - Ending {end_date})...")
        
        # 1. Fetch all historical races in chronological order
        query = self.db.query(RaceModel).options(
            joinedload(RaceModel.entries)
        ).filter(
            RaceModel.date >= start_date
        )
        
        if end_date:
            query = query.filter(RaceModel.date < end_date)
            
        races = query.order_by(RaceModel.date.asc()).all()
        
        count = 0
        for race in races:
            for entry in race.entries:
                self._process_entry(race, entry)
            count += 1
            if count % 50 == 0:
                print(f"Processed {count} races...", end='\r')
            
        print(f"Processed {count} races. Profiles built for {len(self.profiles)} horses.")
        return self.profiles

    def ingest_daily_races(self, target_date: date):
        """
        Incrementally process races for a specific date to update profiles.
        """
        races = self.db.query(RaceModel).options(
            joinedload(RaceModel.entries)
        ).filter(
            RaceModel.date == target_date
        ).all()
        
        updates = 0
        for race in races:
            for entry in race.entries:
                self._process_entry(race, entry)
                updates += 1
        return updates
        
    def _process_entry(self, race: RaceModel, entry: EntryModel):
        name = entry.horse_name
        if name not in self.profiles:
            self.profiles[name] = HorseProfile(horse_name=name)
            
        profile = self.profiles[name]
        
        # Parse AGF if available (None check handled in update)
        # EntryModel.agf is Float or None
        
        profile.update(
            race_date=race.date,
            race_city=race.city,
            surface=race.surface,
            distance=race.distance_m,
            rank=entry.rank,
            agf=entry.agf,
            jockey=entry.jockey_name
        )

