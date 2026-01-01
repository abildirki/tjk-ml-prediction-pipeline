import pandas as pd
import numpy as np

def calculate_specialization_features_v2(df):
    """
    Calculates Track (Surface) and Distance specialization ratios.
    Performance is "Win Rate" under specific conditions vs Global Win Rate.
    Safe-Index implementation.
    """
    # 1. Preserve Original Index
    original_idx = df.index
    
    # 2. Work on sorted copy with clean index
    df_work = df.copy()
    df_work['__orig_index'] = df_work.index
    df_work = df_work.sort_values('date')
    
    # 3. Clean Slate
    df_clean = pd.DataFrame(df_work.to_dict('records'))
    
    # 4. Global Stats
    # Clean Groupby
    grouped = df_clean.groupby('horse', sort=False)
    
    df_clean['is_win'] = (df_clean['rank'] == 1).astype(int)
    
    # Use transform for alignment
    # shift(1).cumsum()
    cum_wins = grouped['is_win'].transform(lambda x: x.shift(1).cumsum()).fillna(0)
    cum_races = grouped.cumcount()
    
    global_win_rate = cum_wins / cum_races.replace(0, 1)
    
    # 5. Surface Specialization
    df_clean['horse_surface'] = df_clean['horse'] + "_" + df_clean['surface']
    surf_grp = df_clean.groupby('horse_surface', sort=False)
    
    surf_wins = surf_grp['is_win'].transform(lambda x: x.shift(1).cumsum()).fillna(0)
    surf_count = surf_grp.cumcount()
    
    surf_win_rate = surf_wins / surf_count.replace(0, 1)
    
    # 6. Distance Specialization
    def dist_bucket(d):
        try:
            d = float(d)
        except: return 'unknown'
        if d < 1300: return 'sprint'
        elif d <= 1700: return 'mile'
        else: return 'long'
        
    df_clean['dist_bucket'] = df_clean['distance'].apply(dist_bucket)
    df_clean['horse_dist'] = df_clean['horse'] + "_" + df_clean['dist_bucket']
    
    dist_grp = df_clean.groupby('horse_dist', sort=False)
    
    dist_wins = dist_grp['is_win'].transform(lambda x: x.shift(1).cumsum()).fillna(0)
    dist_count = dist_grp.cumcount()
    
    dist_win_rate = dist_wins / dist_count.replace(0, 1)
    
    # 7. Assemble Features
    features = pd.DataFrame(index=df_clean.index)
    features['same_track_win_rate'] = surf_win_rate
    features['global_win_rate'] = global_win_rate
    features['track_specialization_ratio'] = (surf_win_rate / global_win_rate.replace(0, 1)).fillna(0)
    
    features['same_dist_win_rate'] = dist_win_rate
    features['dist_specialization_ratio'] = (dist_win_rate / global_win_rate.replace(0, 1)).fillna(0)
    
    # 8. Restore Index
    features.index = df_clean['__orig_index']
    features = features.reindex(original_idx)
    
    return features
