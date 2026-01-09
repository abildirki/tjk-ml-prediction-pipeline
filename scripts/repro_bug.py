import pandas as pd
import numpy as np

def test():
    print("Creating DF...")
    df = pd.DataFrame({
        'horse': ['A', 'A', 'B', 'B', 'C'],
        'date': pd.to_datetime(['2021-01-01', '2021-01-02', '2021-01-01', '2021-01-03', '2021-01-01']),
        'rank': [1, 2, 3, 4, 5],
        'is_win': [1, 0, 0, 0, 0],
        'is_place': [1, 1, 1, 0, 0]
    })
    
    df = df.sort_values(['horse', 'date']).reset_index(drop=True)
    print("DF Index:", df.index)
    
    grouped = df.groupby('horse')
    
    print("Calculating shift...")
    # This matches history.py logic
    try:
        prev_vals = grouped['rank'].shift(1).values
        print("Shift Values Type:", type(prev_vals))
        print("Shift Values Shape:", prev_vals.shape)
        
        df['prev_rank'] = prev_vals
        print("Assignment Success!")
    except Exception as e:
        print(f"Assignment Failed: {e}")
        import traceback
        traceback.print_exc()

    print("Calculating rolling...")
    try:
        res = df.groupby('horse', sort=False)['rank'].rolling(2, min_periods=1).mean()
        print("Rolling Res Index:", res.index)
        
        vals = res.values
        print("Rolling Values Type:", type(vals))
        
        features = pd.DataFrame(index=df.index)
        features['roll'] = vals
        print("Rolling Assignment Success!")
    except Exception as e:
        print(f"Rolling Assignment Failed: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    test()
