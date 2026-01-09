import sys
import os
sys.path.append(os.path.join(os.getcwd(), "src"))
from tjk.storage.db import engine, Base
from sqlalchemy import text

def reset_db():
    # engine is already created in db.py
    with engine.connect() as conn:
        # Disable FK checks to allow dropping tables in any order
        conn.execute(text("PRAGMA foreign_keys = OFF;"))
        
        # Get all tables
        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table';"))
        tables = [row[0] for row in result]
        
        for table in tables:
            if table != 'sqlite_sequence':
                print(f"Dropping table: {table}")
                conn.execute(text(f"DROP TABLE IF EXISTS {table};"))
        
        conn.execute(text("PRAGMA foreign_keys = ON;"))
        conn.commit()
    print("Database reset complete.")

if __name__ == "__main__":
    reset_db()
