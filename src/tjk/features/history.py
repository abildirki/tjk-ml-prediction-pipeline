
import pandas as pd
import numpy as np

def calculate_history_features_v2(df, lookback_windows=[3, 5, 10]):
    """
    Calculates Last-N history features for each horse.
    
    Args:
        df: DataFrame containing all past races.
        lookback_windows: List of N values (e.g., [3, 5])
        
    Returns:
        DataFrame with new feature columns, aligned to input df index.
    """
    # 1. Preserve Original Index for final alignment
    # df might come in with any index (e.g. RangeIndex).
    # We want to return a DF that matches this index exactly.
    original_idx = df.index
    
    # 2. Create Working Copy
    # We add a column to track the original index explicitly
    df_work = df.copy()
    df_work['__orig_index'] = df_work.index
    
    # 3. Sort by Horse/Date
    df_work = df_work.sort_values(['horse', 'date'])
    
    # Calculate binary targets
    df_work['is_win'] = (df_work['rank'] == 1).astype(int)
    df_work['is_place'] = (df_work['rank'] <= 3).astype(int)
    
    # 4. Create Clean Slate for Vectorized Ops
    # We strip the index to generic RangeIndex to avoid any MultiIndex/Alignment issues during rolling
    # But we keep '__orig_index' as a column
    df_clean = pd.DataFrame(df_work.to_dict('records'))
    
    # 5. Group and Shift
    grouped = df_clean.groupby('horse', sort=False) # df_clean is sorted by horse
    
    # Vectorized shifts (using .values to avoid index issues)
    prev_rank = grouped['rank'].shift(1).values
    prev_win = grouped['is_win'].shift(1).values
    prev_place = grouped['is_place'].shift(1).values
    
    # 6. Add shifts to df_clean safely
    df_clean['prev_rank'] = prev_rank
    df_clean['prev_win'] = prev_win
    df_clean['prev_place'] = prev_place
    
    # 7. Rolling Calculations using loop
    features_dict = {}
    
    # Re-group (on the now modified df_clean)
    grouped_rolling = df_clean.groupby('horse', sort=False)
    
    for n in lookback_windows:
        def calc_roll(col):
            return grouped_rolling[col].rolling(n, min_periods=1).mean().values
            
        features_dict[f'avg_rank_last{n}'] = calc_roll('prev_rank')
        features_dict[f'win_rate_last{n}'] = calc_roll('prev_win')
        features_dict[f'place_rate_last{n}'] = calc_roll('prev_place')
        
    # 8. Create Result DataFrame
    # Initial creation with df_clean's RangeIndex
    features = pd.DataFrame(features_dict, index=df_clean.index)
    
    # 9. Restore Original Index Alignment
    # df_clean['__orig_index'] holds the original index values in the sorted order.
    features.index = df_clean['__orig_index']
    
    # 10. Reindex to match INPUT df order
    # This ensures that features[0] corresponds to input_df[0]
    features = features.reindex(original_idx)
    
    # Fill NAs
    features = features.fillna(-1)
    
    return features
