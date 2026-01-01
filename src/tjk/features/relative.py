import pandas as pd
import numpy as np

def calculate_relative_features(df):
    """
    Calculates features relative to the specific race field.
    e.g. Weight vs Avg Weight, HP vs Avg HP.
    """
    # Group by Race ID (date + city + raceno)
    # We don't have a specific race_id column in dataset loader yet, 
    # but (date, city, race_no) is the key.
    
    group_cols = ['date', 'city', 'race_no']
    grouped = df.groupby(group_cols)
    
    features = pd.DataFrame(index=df.index)
    
    # Weight Relative
    # Fill NA weights with mean? NO, better to leave or 58 default?
    # Let's fill with group mean.
    df['weight_filled'] = grouped['weight'].transform(lambda x: x.fillna(x.mean()))
    
    # Field Average Weight
    field_avg_weight = grouped['weight_filled'].transform('mean')
    features['relative_weight'] = df['weight_filled'] - field_avg_weight
    
    # HP Relative
    # Fill NA HP with 40 (unknown/debut)? 
    # Or group min? Let's use 0 for safe math.
    df['hp_filled'] = df['hp'].fillna(0)
    field_avg_hp = grouped['hp_filled'].transform('mean')
    features['relative_hp'] = df['hp_filled'] - field_avg_hp
    
    # Percentiles (Rank within field before race)
    # e.g. Rank 1 = Highest HP.
    features['hp_rank_in_race'] = grouped['hp_filled'].rank(ascending=False)
    features['weight_rank_in_race'] = grouped['weight_filled'].rank(ascending=False) # 1 = Heaviest
    
    # Field Size (Context)
    features['field_size'] = grouped['horse'].transform('count')
    
    return features
