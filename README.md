# TJK V2 – Dual-Source Scraper & ML Prediction Pipeline

Automated dual-source data collection and an end-to-end machine learning pipeline for TJK (horse racing) data.
Includes smart-resume scraping, dataset building, feature engineering, and model training/evaluation.

## Why this project?
Manual data collection and ad-hoc model training are slow and error-prone. This project provides:
- **Automated scraping** from multiple sources (with retry + smart resume)
- **Structured storage** (SQLite) for reproducible datasets
- **ML pipeline** with feature engineering and evaluation flow
- A foundation to extend into backtesting, reporting, and UI tooling

## Key Features
- Dual-source web scraping (resilient: retries, resume)
- SQLite-based persistence (consistent datasets)
- Dataset preparation + feature engineering
- Model training (XGBoost / LightGBM) and evaluation
- CLI-style utilities for inspecting DB and running tasks

## Tech Stack
- Python 3.10+
- httpx, selectolax (scraping)
- pandas, scikit-learn (data/ML)
- xgboost, lightgbm (models)
- SQLite (storage)

---

## Project Structure (high level)
> Names may vary slightly depending on your repo.

- `src/` → core source code
- `tjk/` → pipeline + CLI modules (if used)
- `run_scrape.py` → main scraper entry (smart resume)
- `*.py` scripts → training / analysis / reporting utilities
- `requirements.txt` → dependencies

---

## Setup

### 1) Environment
- Python **3.10+** recommended

### 2) Install dependencies
```bash
pip install -r requirements.txt
