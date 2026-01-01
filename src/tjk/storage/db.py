from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from ..config import settings

class Base(DeclarativeBase):
    pass

engine = create_engine(settings.DB_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    from . import schema # Ensure models are loaded
    Base.metadata.create_all(bind=engine)
