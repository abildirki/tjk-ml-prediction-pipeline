import pandas as pd
import numpy as np
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

def prepare_features(df):
    """
    Applies feature engineering to the raw dataframe.
    Calculates rolling stats, relative metrics, etc.
    """
    print("🛠️  Feature Engineering started...")

    # Ensure sorting for rolling calculations
    df['race_date'] = pd.to_datetime(df['race_date'])
    df = df.sort_values(['horse_name', 'race_date'])
    # FIX: Reset index so that subsequent rolling calculations (which use reset_index)
    # align correctly with the DataFrame.
    df = df.reset_index(drop=True)

    # Basic Cleaning
    df['rank'] = pd.to_numeric(df['rank'], errors='coerce')
    df['hp'] = pd.to_numeric(df['hp'], errors='coerce').fillna(0)
    df['weight_kg'] = pd.to_numeric(df['weight_kg'], errors='coerce').fillna(50)
    df['agf'] = pd.to_numeric(df['agf'], errors='coerce').fillna(0)

    # 1. History Stats (Avg Rank Last 3/5)
    # We use shift(1) to ensure we don't use current race result in features
    # (Past performance only)

    # Helper to calculate rolling mean of 'rank'
    # Since rank can be None (if DNF), we handle that.
    # Actually, let's treat unplaced or DNF as a high rank (e.g. 15) for stats?
    # Or just ignore. Ignoring is safer for 'average place'.

    # Create a numeric rank for stats where DNF is penalized
    df['stat_rank'] = df['rank'].fillna(15)

    # Rolling averages - Correctly scoped per horse using transform
    # Shift 1 to exclude current race
    df['avg_rank_last3'] = df.groupby('horse_name')['stat_rank'].transform(
        lambda x: x.shift(1).rolling(window=3, min_periods=1).mean()
    )
    df['avg_rank_last5'] = df.groupby('horse_name')['stat_rank'].transform(
        lambda x: x.shift(1).rolling(window=5, min_periods=1).mean()
    )

    # Win/Place Rates (Last 5)
    # 1 if rank=1 else 0
    df['is_win'] = (df['rank'] == 1).astype(int)
    df['is_place'] = (df['rank'] <= 3).astype(int)

    df['win_rate_last5'] = df.groupby('horse_name')['is_win'].transform(
        lambda x: x.shift(1).rolling(window=5, min_periods=1).mean()
    )
    df['place_rate_last5'] = df.groupby('horse_name')['is_place'].transform(
        lambda x: x.shift(1).rolling(window=5, min_periods=1).mean()
    )

    # Fill initial NaNs (first races)
    df['avg_rank_last3'] = df['avg_rank_last3'].fillna(10.0)
    df['avg_rank_last5'] = df['avg_rank_last5'].fillna(10.0)
    df['win_rate_last5'] = df['win_rate_last5'].fillna(0.0)
    df['place_rate_last5'] = df['place_rate_last5'].fillna(0.0)

    # 2. Specialization (Track / Distance)
    # Simple cumulative mean of win/place on this surface
    # This is harder to do vectorized without data leakage.
    # Expanding mean (cumulative average) up to previous row.

    # Same Track Win Rate - Expanding Mean
    # Note: We need to group by both horse and surface, but we want the result aligned to the main df.
    # .transform handles alignment automatically.

    df['same_track_win_rate'] = df.groupby(['horse_name', 'surface'])['is_win'].transform(
        lambda x: x.shift(1).expanding(min_periods=1).mean()
    ).fillna(0)

    # Track Specialization Ratio: (Track Win Rate) / (Global Win Rate + epsilon)
    # Global win rate per horse
    global_win_rate = df.groupby('horse_name')['is_win'].transform(
        lambda x: x.shift(1).expanding(min_periods=1).mean()
    ).fillna(0)

    df['track_specialization_ratio'] = df['same_track_win_rate'] / (global_win_rate + 0.01)

    # Distance Specialization (bins: Short < 1300, Middle < 1900, Long >= 1900)
    df['dist_cat'] = pd.cut(df['distance_m'], [-1, 1300, 1900, 10000], labels=['short', 'middle', 'long'])

    # Distance Win Rate
    # Note: groupby on multiple columns including a categorical one works fine with transform
    # provided we observe=False or convert to string if issues arise.
    # Using observed=False explicitly to handle categorical warnings
    df['dist_win_rate'] = df.groupby(['horse_name', 'dist_cat'], observed=False)['is_win'].transform(
        lambda x: x.shift(1).expanding(min_periods=1).mean()
    ).fillna(0)

    df['dist_specialization_ratio'] = df['dist_win_rate'] / (global_win_rate + 0.01)

    # 3. Relative Features (in this race)
    # We need to group by Race (Date+City+RaceNo) and calculate ranks/diffs

    # Rank of Weight in Race (1 = heaviest)
    # df.groupby('race_id')['weight_kg'].rank(ascending=False)
    # Note: we need a race_id. The raw query has r.date, r.city, r.race_no
    # Let's create a temp ID
    df['temp_race_id'] = df['race_date'].astype(str) + "_" + df['city'] + "_" + df['race_no'].astype(str)

    df['relative_weight'] = df.groupby('temp_race_id')['weight_kg'].transform(lambda x: (x - x.mean()) / (x.std() + 1e-6))
    df['relative_hp'] = df.groupby('temp_race_id')['hp'].transform(lambda x: (x - x.mean()) / (x.std() + 1e-6))

    df['hp_rank_in_race'] = df.groupby('temp_race_id')['hp'].rank(ascending=False)
    df['field_size'] = df.groupby('temp_race_id')['horse_name'].transform('count')

    # 4. Target Clean up
    df['is_top3'] = (df['rank'] <= 3).astype(int)

    # Clean up temp cols
    drop_cols = ['stat_rank', 'is_win', 'is_place', 'dist_cat', 'dist_win_rate', 'temp_race_id']
    df = df.drop(columns=[c for c in drop_cols if c in df.columns])

    # Final NaN check for features
    fill_zeros = ['relative_weight', 'relative_hp', 'hp_rank_in_race', 'field_size']
    for c in fill_zeros:
        df[c] = df[c].fillna(0)

    print("✅ Feature Engineering complete.")
    return df
