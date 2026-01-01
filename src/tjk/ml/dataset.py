import pandas as pd
from sqlalchemy import text
from tjk.storage.db import get_db

# Central Column Mapping
# DB Column -> ML Feature Name
COLUMN_MAPPING = {
    'race_date': 'date',      # implied from race join
    'city': 'city',
    'race_no': 'race_no',
    'surface': 'surface',
    'distance_m': 'distance',
    'horse_name': 'horse',
    'jockey_name': 'jockey',
    'trainer_id': 'trainer',
    'weight_kg': 'weight',
    'hp': 'hp',
    'agf': 'agf',
    'form_score': 'form_score',
    # Targets
    'rank': 'rank',
    'finish_time': 'finish_time',
}

def inspect_db():
    """Reads all tables and prints columns/types to help build the mapping."""
    db = next(get_db())
    print("\n🧐 INSPECTING DATABASE SCHEMA...\n")
    
    tables = ['races', 'entries', 'horses']
    
    for t_name in tables:
        print(f"--- TABLE: {t_name.upper()} ---")
        try:
            # Get columns info
            cols = db.execute(text(f"PRAGMA table_info({t_name})")).fetchall()
            # cid, name, type, notnull, dflt_value, pk
            for c in cols:
                print(f"  - {c[1]:<15} ({c[2]})")
                
            # Count rows
            count = db.execute(text(f"SELECT count(*) FROM {t_name}")).scalar()
            print(f"  > ROW COUNT: {count}")
            
            # Sample data
            print(f"  > SAMPLE:")
            df = pd.read_sql(text(f"SELECT * FROM {t_name} LIMIT 3"), db.connection())
            print(df.to_string(index=False))
            print("\n")
            
        except Exception as e:
            print(f"  ERROR: {e}\n")

def load_raw_data(start_date=None, end_date=None):
    """
    Loads raw data joining Races + Entries.
    Leakage Warning: This returns RAW data. Feature engineering must handle dates carefully.
    """
    db = next(get_db())
    
    query = """
    SELECT 
        r.date as race_date, r.city, r.race_no, r.surface, r.distance_m,
        e.* 
    FROM entries e
    JOIN races r ON e.race_id = r.race_id
    """
    
    # Simple date filter if provided
    params = {}
    where = []
    if start_date:
        where.append("r.date >= :start")
        params['start'] = start_date
    if end_date:
        where.append("r.date <= :end")
        params['end'] = end_date
        
    if where:
        query += " WHERE " + " AND ".join(where)
        
    query += " ORDER BY r.date, r.city, r.race_no"
    
    print(f"⏳ Loading data from DB ({start_date} to {end_date})...")
    df = pd.read_sql(text(query), db.connection(), params=params)
    print(f"✅ Loaded {len(df)} rows.")
    return df
