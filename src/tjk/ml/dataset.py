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

def parse_finish_time(time_str):
    """
    Parses '1.35.22' or '2.14.05' format to seconds (float).
    Returns None if invalid.
    """
    if not isinstance(time_str, str) or not time_str:
        return None

    try:
        parts = time_str.replace(':', '.').split('.')
        # Case 1: Minutes.Seconds.Hundredths (e.g., 1.35.22)
        if len(parts) == 3:
            minutes = int(parts[0])
            seconds = int(parts[1])
            hundredths = int(parts[2])
            return minutes * 60 + seconds + hundredths / 100.0

        # Case 2: Seconds.Hundredths (rare but possible for very short races?)
        elif len(parts) == 2:
            seconds = int(parts[0])
            hundredths = int(parts[1])
            return seconds + hundredths / 100.0

        return None
    except:
        return None

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

    # --- Speed Ratings ---
    df['finish_seconds'] = df['finish_time'].apply(parse_finish_time)

    # Group by Surface + Distance (rounded to nearest 100m) to find average times
    # We use a broader bucket to get enough data points
    df['dist_bucket'] = (df['distance_m'] / 100).round() * 100

    # Calculate Average Time for this Track Condition (Surface + Dist Bucket)
    # We must not use future data!
    # Use expanding mean of finish_seconds per (City, Surface, Dist Bucket)
    # Group by City+Surface+Dist
    # We need to sort by date globally first? It's already sorted by horse.
    # We need to re-sort by date to calculate track averages correctly over time.

    # Create a temp sorted view for track stats
    # To assign back, we can use an index map or merge.
    # Easiest way: Use transform on a date-sorted df, but our df is horse-sorted.
    # Let's do horse stats first, then re-sort for track stats, then re-sort/merge?

    # 1. Horse History Stats (Avg Rank Last 3/5)
    # We use shift(1) to ensure we don't use current race result in features
    # (Past performance only)

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
    df['is_win'] = (df['rank'] == 1).astype(int)
    df['is_place'] = (df['rank'] <= 3).astype(int)

    df['win_rate_last5'] = df.groupby('horse_name')['is_win'].transform(
        lambda x: x.shift(1).rolling(window=5, min_periods=1).mean()
    )
    df['place_rate_last5'] = df.groupby('horse_name')['is_place'].transform(
        lambda x: x.shift(1).rolling(window=5, min_periods=1).mean()
    )

    # Fill initial NaNs
    df['avg_rank_last3'] = df['avg_rank_last3'].fillna(10.0)
    df['avg_rank_last5'] = df['avg_rank_last5'].fillna(10.0)
    df['win_rate_last5'] = df['win_rate_last5'].fillna(0.0)
    df['place_rate_last5'] = df['place_rate_last5'].fillna(0.0)

    # 2. Specialization (Track / Distance)
    df['same_track_win_rate'] = df.groupby(['horse_name', 'surface'])['is_win'].transform(
        lambda x: x.shift(1).expanding(min_periods=1).mean()
    ).fillna(0)

    # Global win rate per horse
    global_win_rate = df.groupby('horse_name')['is_win'].transform(
        lambda x: x.shift(1).expanding(min_periods=1).mean()
    ).fillna(0)

    df['track_specialization_ratio'] = df['same_track_win_rate'] / (global_win_rate + 0.01)

    # Distance Specialization
    df['dist_cat'] = pd.cut(df['distance_m'], [-1, 1300, 1900, 10000], labels=['short', 'middle', 'long'])

    df['dist_win_rate'] = df.groupby(['horse_name', 'dist_cat'], observed=False)['is_win'].transform(
        lambda x: x.shift(1).expanding(min_periods=1).mean()
    ).fillna(0)

    df['dist_specialization_ratio'] = df['dist_win_rate'] / (global_win_rate + 0.01)

    # --- Speed Ratings Implementation ---
    # We need to normalize finish_seconds.
    # Group by [City, Surface, Dist_Bucket] and calculate Expanding Mean of finish_seconds
    # BUT we need to respect time order.
    # Current sort order is Horse -> Date.
    # We need to sort by Date -> City ... for this calc.

    # Let's save the current index to restore later? Or just re-sort at end.
    # Re-sorting is safer.

    df = df.sort_values(['race_date', 'city', 'race_no'])

    # Calculate Track Average Time (Expanding)
    # Excluding current race is hard row-by-row efficiently.
    # But for a "standard" time, we can use the historical average up to yesterday?
    # Or simpler: Global average for that track/dist from training set?
    # Let's use expanding mean.

    track_grp = df.groupby(['city', 'surface', 'dist_bucket'])['finish_seconds']
    df['track_avg_time'] = track_grp.transform(lambda x: x.expanding().mean())

    # Speed Score: (TrackAvg - HorseTime) / TrackAvg * 100
    # Positive is faster (time < avg).
    # We use 'shift(1)' logic implicitly if we wanted prediction, but here 'finish_seconds' is the target for PAST races.
    # We want to feature: "Average Speed Rating in Last 3 Races".
    # So first we calculate Speed Rating for every row (using its own time),
    # THEN we aggregate it rolling for the next race.

    # Use the current race's time to compute the rating for this race record
    df['speed_rating'] = (df['track_avg_time'] - df['finish_seconds']) / df['track_avg_time'] * 1000
    df['speed_rating'] = df['speed_rating'].fillna(0)

    # Now roll this Speed Rating forward for the horse
    # Sort back to Horse -> Date
    df = df.sort_values(['horse_name', 'race_date'])

    df['avg_speed_last3'] = df.groupby('horse_name')['speed_rating'].transform(
        lambda x: x.shift(1).rolling(window=3, min_periods=1).mean()
    ).fillna(0)

    # --- Jockey & Trainer Stats ---
    # Jockey Win Rate (Last 100 rides)
    # We need to sort by Date globally again? Or just grouped by Jockey -> Date.
    df = df.sort_values(['jockey_name', 'race_date'])
    df['jockey_win_rate'] = df.groupby('jockey_name')['is_win'].transform(
        lambda x: x.shift(1).rolling(window=100, min_periods=10).mean()
    ).fillna(0)

    # Trainer Win Rate
    df = df.sort_values(['trainer_id', 'race_date'])
    df['trainer_win_rate'] = df.groupby('trainer_id')['is_win'].transform(
        lambda x: x.shift(1).rolling(window=100, min_periods=10).mean()
    ).fillna(0)

    # 3. Relative Features (in this race)
    # Re-sort to date/race for relative calc
    df = df.sort_values(['race_date', 'city', 'race_no'])

    df['temp_race_id'] = df['race_date'].astype(str) + "_" + df['city'] + "_" + df['race_no'].astype(str)

    df['relative_weight'] = df.groupby('temp_race_id')['weight_kg'].transform(lambda x: (x - x.mean()) / (x.std() + 1e-6))
    df['relative_hp'] = df.groupby('temp_race_id')['hp'].transform(lambda x: (x - x.mean()) / (x.std() + 1e-6))

    df['hp_rank_in_race'] = df.groupby('temp_race_id')['hp'].rank(ascending=False)
    df['field_size'] = df.groupby('temp_race_id')['horse_name'].transform('count')

    # 4. Target Clean up
    df['is_top3'] = (df['rank'] <= 3).astype(int)

    # Clean up temp cols
    drop_cols = ['stat_rank', 'is_win', 'is_place', 'dist_cat', 'dist_win_rate', 'temp_race_id',
                 'finish_seconds', 'track_avg_time', 'speed_rating', 'dist_bucket']
    df = df.drop(columns=[c for c in drop_cols if c in df.columns])

    # Final NaN check for features
    fill_zeros = ['relative_weight', 'relative_hp', 'hp_rank_in_race', 'field_size']
    for c in fill_zeros:
        df[c] = df[c].fillna(0)

    print("✅ Feature Engineering complete.")
    return df
