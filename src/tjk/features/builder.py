
import pandas as pd
from tjk.ml.dataset import load_raw_data, COLUMN_MAPPING
from tjk.features.history import calculate_history_features_v2

from tjk.features.specialization import calculate_specialization_features_v2
from tjk.features.relative import calculate_relative_features
# from tjk.features.surprise import calculate_surprise_features

def build_features_for_dataset(start_date=None, end_date=None):
    """
    Main pipeline to load DB data and generate ALL features.
    """
    # 1. Load Raw Data
    df = load_raw_data(start_date, end_date)
    
    # Rename cols based on mapping
    # dataset.py loaded with raw DB names, let's normalize
    # Actually load_raw_data uses 'r.date as race_date', let's stick to our conventions
    # COLUMN_MAPPING was: 'race_date' -> 'date'
    
    # Apply mapping normalization
    # Reverse mapping for rename? 
    # dataset.py: 'race_date': 'date'
    rename_dict = {k:v for k,v in COLUMN_MAPPING.items() if k in df.columns}
    df = df.rename(columns=rename_dict)
    
    # Ensure date usage
    df['date'] = pd.to_datetime(df['date'])
    
    print("\n🛠️ BUILDING FEATURES...")
    
    # 2. History Features
    print("  > 1/3 History (Last N)...")
    # Using v2 (Fixed with Reindexing)
    df_hist = calculate_history_features_v2(df)
    
    # 3. Specialization Features
    print("  > 2/3 Specialization (Track/Dist)...")
    df_spec = calculate_specialization_features_v2(df)
    
    # 4. Relative Features
    print("  > 3/3 Relative (In-Race)...")
    df_rel = calculate_relative_features(df)
    
    # 5. Merge All
    # Indexes should align perfectly as we didn't drop rows (filled NA)
    print(f"DEBUG: Builder - Hist Index: {df_hist.index}")
    print(f"DEBUG: Builder - Spec Index: {df_spec.index}")
    print(f"DEBUG: Builder - Rel Index: {df_rel.index}")
    print(f"DEBUG: Builder - Main DF Index: {df.index}")
    
    # Combine
    # Note: We must ensure indices align.
    # df_hist was created from sorted df.
    # We must join on index?
    # Or did sub-functions sort df?
    
    # Concatenate columns
    all_features = pd.concat([df, df_hist, df_spec, df_rel], axis=1)
    
    # Drop "duplicate" cols if any (concat usually handles unique names)
    # Check for empty cols
    full_df = all_features.loc[:, ~all_features.columns.duplicated()]
    
    print(f"✅ Feature Engineering Complete. Shape: {full_df.shape}")
    return full_df
