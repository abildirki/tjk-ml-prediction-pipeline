from sqlalchemy.orm import Session
from sqlalchemy.dialects.sqlite import insert
from .schema import RaceModel, EntryModel, HorseModel
from ..models.race import Race
from ..models.horse import HorseProfile

class TJKRepository:
    def __init__(self, db: Session):
        self.db = db

    def upsert_program_race(self, race: Race):
        # 1. Race Upsert
        existing_race = self.db.query(RaceModel).filter(RaceModel.race_id == race.race_id).first()
        if existing_race:
            self.db.delete(existing_race)
            self.db.commit()
            
        db_race = RaceModel(
            race_id=race.race_id,
            date=race.date,
            city=race.city,
            race_no=race.race_no,
            distance_m=race.distance_m,
            surface=race.surface.value
        )
        self.db.add(db_race)
        self.db.commit()
        
        # 2. Entries Upsert
        for entry in race.entries:
            # Handle Horse Profile Updates (Pedigree, Age->BirthYear)
            temp_info = getattr(entry, '_temp_horse_info', {})
            birth_year = None
            if temp_info.get('age_text'):
                try:
                    # "4y d a" -> 4 -> 2025 - 4 = 2021
                    age_str = temp_info['age_text'].split('y')[0]
                    age = int(age_str)
                    birth_year = race.date.year - age
                except: pass
                
            horse_profile = HorseProfile(
                horse_id=entry.horse_id,
                name=entry.horse_name,
                sire=temp_info.get('sire'),
                dam=temp_info.get('dam'),
                birth_year=birth_year,
                # gender argument omitted, uses default Gender.UNKNOWN
            )
            self.upsert_horse(horse_profile)

            # Insert Entry
            db_entry = EntryModel(
                race_id=race.race_id,
                horse_id=entry.horse_id,
                horse_name=entry.horse_name,
                saddle_no=entry.saddle_no,
                jockey_name=entry.jockey_name,
                weight_kg=entry.weight_kg,
                owner_id=entry.owner_id,
                trainer_id=entry.trainer_id,
                hp=entry.hp,
                kgs=entry.kgs,
                s20=entry.s20,
                agf=entry.agf,
                form_score=entry.form_score,
                equipment=entry.equipment
                # Rank/Time are Null initially
            )
            self.db.add(db_entry)
        self.db.commit()

    def update_race_results(self, race: Race):
        # Only update Rank, Time, Ganyan, Equipment for existing entries
        for entry in race.entries:
            # Find matching entry by ID (preferred) or Name
            db_entry = self.db.query(EntryModel).filter(
                EntryModel.race_id == race.race_id,
                EntryModel.horse_id == entry.horse_id
            ).first()
            
            if db_entry:
                db_entry.rank = entry.rank
                db_entry.finish_time = entry.finish_time
                db_entry.ganyan = entry.ganyan
                # Update equipment if provided in results (might differ from program)
                if entry.equipment:
                    db_entry.equipment = entry.equipment
            else:
                # Fallback: If entry wasn't in program (rare late entry?), insert it?
                # For now, just log or skip.
                print(f"Warning: Result entry {entry.horse_name} not found in program entries.")
                pass
        self.db.commit()

    def upsert_horse(self, horse: HorseProfile):
        existing = self.db.query(HorseModel).filter(HorseModel.horse_id == horse.horse_id).first()
        if not existing:
            db_horse = HorseModel(
                horse_id=horse.horse_id,
                name=horse.name,
                gender=horse.gender.value if horse.gender else None,
                sire=horse.sire,
                dam=horse.dam,
                birth_year=horse.birth_year
            )
            self.db.add(db_horse)
        else:
            # Update missing info
            if horse.sire and not existing.sire: existing.sire = horse.sire
            if horse.dam and not existing.dam: existing.dam = horse.dam
            if horse.birth_year and not existing.birth_year: existing.birth_year = horse.birth_year
            
        self.db.commit()
