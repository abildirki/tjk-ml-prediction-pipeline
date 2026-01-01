# TJK V2 & ML Pipeline

Automated dual-source scraper and machine learning pipeline for TJK horse racing data.

## Setup

1. **Environment**: Python 3.10+
2. **Installation**:
   ```bash
   pip install -r requirements.txt
   # ML Dependencies
   pip install scikit-learn xgboost
   # Optional
   pip install lightgbm
   ```

## Usage

### Scraper
Run the full automated scrape (Smart Resume):
```bash
python run_scrape.py
```

### ML Pipeline (New)

**1. Inspect Database columns:**
```bash
python -m tjk.cli inspect-db
```

**2. Run Backtest:**
```bash
python -m tjk.cli backtest --start 2025-05-05 --end 2025-12-19
```

**3. Predict Today:**
```bash
python -m tjk.cli predict-day --date 2025-12-19
```

## Structure
- `src/tjk/storage`: Database layer (Do not modify).
- `src/tjk/features`: Feature engineering logic.
- `src/tjk/ml`: Machine learning core (Trainer, Splitter).
- `src/tjk/backtest`: Walk-forward backtesting.
