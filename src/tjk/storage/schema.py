from sqlalchemy import Column, String, Integer, Float, Date, ForeignKey, JSON
from sqlalchemy.orm import relationship
from .db import Base

class RaceModel(Base):
    __tablename__ = "races"
    
    race_id = Column(String, primary_key=True, index=True)
    date = Column(Date, nullable=False)
    city = Column(String, nullable=False)
    race_no = Column(Integer, nullable=False)
    distance_m = Column(Integer)
    surface = Column(String)
    entries = relationship("EntryModel", back_populates="race", cascade="all, delete-orphan")

class EntryModel(Base):
    __tablename__ = "entries"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    race_id = Column(String, ForeignKey("races.race_id"), nullable=False)
    horse_id = Column(String, nullable=False)
    horse_name = Column(String, nullable=False)
    saddle_no = Column(Integer)
    jockey_name = Column(String)
    weight_kg = Column(Float)
    owner_id = Column(String, nullable=True)
    trainer_id = Column(String, nullable=True)
    hp = Column(Integer, nullable=True)
    kgs = Column(Integer, nullable=True)
    s20 = Column(Integer, nullable=True)
    agf = Column(Float, nullable=True)
    form_score = Column(String, nullable=True)
    
    # Result fields
    rank = Column(Integer, nullable=True)
    finish_time = Column(String, nullable=True)
    ganyan = Column(String, nullable=True) # "3.45"
    equipment = Column(String, nullable=True)
    
    race = relationship("RaceModel", back_populates="entries")

class HorseModel(Base):
    __tablename__ = "horses"
    
    horse_id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    gender = Column(String)
    sire = Column(String)
    dam = Column(String)
    birth_year = Column(Integer) # Derived from '4y da' -> 2025 - 4 = 2021
