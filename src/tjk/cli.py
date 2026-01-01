import typer
import asyncio
from datetime import date, timedelta
from .http.client import TJKClient
from .parsers.program_parser import ProgramParser, ProgramCsvParser
from .parsers.csv_parser import CsvParser
from .storage.db import init_db, get_db
from .storage.repo import TJKRepository
from .config import settings

app = typer.Typer()

async def process_city_dual_source(client, target_date: date, city: str):
    """
    Two-phase scraping:
    1. Fetch 'GunlukYarisProgrami' -> Upsert Race/Entries (with AGF, Form, etc.)
    2. Fetch 'GunlukYarisSonuclari' -> Update Race/Entries (with Rank, Time)
    """
    
    # 1. City Name Normalization
    city_map = {
        "IZMIR": "İzmir", "ISTANBUL": "İstanbul", "ANKARA": "Ankara", 
        "BURSA": "Bursa", "ADANA": "Adana", "KOCAELI": "Kocaeli", 
        "ANTALYA": "Antalya", "DIYARBAKIR": "Diyarbakır", 
        "SANLIURFA": "Şanlıurfa", "ELAZIG": "Elazığ"
    }
    upper_city = city.upper().replace('İ', 'I').replace('Ğ', 'G').replace('Ü', 'U').replace('Ş', 'S').replace('Ö', 'O').replace('Ç', 'C')
    normalized_city = city_map.get(upper_city, city.capitalize())
    if upper_city not in city_map: normalized_city = city 

    date_path = target_date.strftime('%Y-%m-%d')
    date_file = target_date.strftime('%d.%m.%Y')
    year = target_date.year
    
    db = next(get_db())
    repo = TJKRepository(db)
    
    # --- PHASE 1: PROGRAM ---
    prog_url = f"https://medya-cdn.tjk.org/raporftp/TJKPDF/{year}/{date_path}/CSV/GunlukYarisProgrami/{date_file}-{normalized_city}-GunlukYarisProgrami-TR.csv"
    try:
        content = await client.get(prog_url)
        parser = ProgramCsvParser()
        races = parser.parse_csv(content, target_date, normalized_city)
        if races:
            for race in races:
                repo.upsert_program_race(race)
            print(f"  [Program] {city}: {len(races)} races upserted.")
        else:
            print(f"  [Program] {city}: Parsed 0 races.")
    except Exception as e:
        print(f"  [Program] {city}: CSV not found/Failed ({e})")
        # Proceed to Results? If Program fails, we can't update results reliably if entries aren't created.
        # But maybe 'upsert_program_race' handles skeleton creation.
        # If Program fails, we skip Results because we rely on existing entries for ID matching?
        # Or we could let Results create entries if missing?
        # My current 'update_race_results' only updates. So we skip.
        # However, for old dates or foreign races, maybe Program CSV is missing but Results exists?
        # TJK usually has both or neither.
        pass

    # --- PHASE 2: RESULTS ---
    res_url = f"https://medya-cdn.tjk.org/raporftp/TJKPDF/{year}/{date_path}/CSV/GunlukYarisSonuclari/{date_file}-{normalized_city}-GunlukYarisSonuclari-TR.csv"
    try:
        content = await client.get(res_url)
        parser = CsvParser()
        races_res = parser.parse_csv(content, target_date, normalized_city)
        if races_res:
            count = 0
            for race in races_res:
                repo.update_race_results(race)
                count += len(race.entries)
            print(f"  [Results] {city}: Updated {count} entries.")
        else:
            print(f"  [Results] {city}: Parsed 0 races.")
    except Exception as e:
        print(f"  [Results] {city}: CSV not found/Failed ({e})")

async def scrape_range_async(start_date: date, end_date: date):
    print(f"Scraping range: {start_date} to {end_date}")
    init_db()
    client = TJKClient()
    program_parser = ProgramParser() 
    
    current_date = start_date
    while current_date <= end_date:
        print(f"\nProcessing {current_date}...")
        try:
            # Discover Cities
            discovery_url = f"{settings.BASE_URL}/TR/YarisSever/Info/Page/GunlukYarisProgrami?QueryParameter_Tarih={current_date.strftime('%d/%m/%Y')}"
            html = await client.get(discovery_url)
            cities = program_parser.parse_cities(html)
            
            if not cities:
                print(f"No cities found for {current_date}")
            else:
                found_names = [c['name'] for c in cities]
                print(f"Found cities: {found_names}")
                
                for city_info in cities:
                    city_name = city_info['name'].split('(')[0].strip()
                    await process_city_dual_source(client, current_date, city_name)
                    
        except Exception as e:
            print(f"Error processing {current_date}: {e}")
            
        current_date += timedelta(days=1)
        await asyncio.sleep(1)
        
    await client.close()

@app.command()
def inspect_db():
    from tjk.ml.dataset import inspect_db as run_inspect
    run_inspect()

@app.command()
def backtest(
    start: str = typer.Option(..., help="Start date YYYY-MM-DD"),
    end: str = typer.Option(..., help="End date YYYY-MM-DD")
):
    from tjk.backtest.runner import run_daily_backtest
    run_daily_backtest(start, end)

@app.command()
def predict_day(date: str):
    """Predict for a specific day (Simulation mode)"""
    # Just run backtest for 1 day
    from tjk.backtest.runner import run_daily_backtest
    run_daily_backtest(date, date)

    """Scrape a date range. Format: YYYY-MM-DD"""
    s = date.fromisoformat(start)
    e = date.fromisoformat(end)
    asyncio.run(scrape_range_async(s, e))

@app.command()
def evaluate():
    """
    Calculates metrics (AUC, HitRate) from backtest reports.
    """
    from tjk.ml.evaluate import run_evaluation
    run_evaluation()

@app.command()
def simulate(
    start: str = typer.Option(..., help="Start date YYYY-MM-DD"),
    end: str = typer.Option(..., help="End date YYYY-MM-DD"),
    train_window: str = typer.Option("all", help="Training window in days or 'all'"),
    resume: bool = typer.Option(False, help="Resume from last state")
):
    """
    True Walk-Forward Simulator (Pseudo-Live).
    """
    from tjk.sim.walk_forward import DailySimulator
    from tjk.reports.stability import generate_stability_report
    
    sim = DailySimulator(start, end, train_window, resume)
    sim.run()
    
    # Auto-generate report at end
    generate_stability_report()

@app.command()
def ticket(
    date: str = typer.Option(None, help="Specific date YYYY-MM-DD"),
    start: str = typer.Option(None, help="Start date YYYY-MM-DD"),
    end: str = typer.Option(None, help="End date YYYY-MM-DD"),
):
    """
    Generates betting tickets (coupons) from predictions.
    """
    from tjk.ticket.composer import TicketComposer
    import pandas as pd
    from datetime import datetime, timedelta
    import os
    import glob

    composer = TicketComposer()
    
    # Locate prediction files
    # Priority: 1. outputs/sim/daily/ (Better, has full risk metrics usually)
    #           2. outputs/daily_reports/
    
    dates_to_process = []
    
    if date:
        dates_to_process.append(date)
    elif start and end:
        s = pd.to_datetime(start)
        e = pd.to_datetime(end)
        while s <= e:
            dates_to_process.append(s.strftime("%Y-%m-%d"))
            s += timedelta(days=1)
            
    print(f"🎫 Generating tickets for {len(dates_to_process)} days...")
    
    for d in dates_to_process:
        # Find file
        # Try Sim Dir first
        sim_path = f"outputs/sim/daily/{d}_predictions.csv"
        rep_path = f"outputs/daily_reports/{d}.csv"
        
        target_path = None
        if os.path.exists(sim_path):
            target_path = sim_path
        elif os.path.exists(rep_path):
            target_path = rep_path
            
        if target_path:
            print(f"  > Processing {d} (Source: {target_path})")
            composer.generate_ticket(target_path, d)
        else:
            print(f"  ⚠️ No predictions found for {d}")

if __name__ == "__main__":
    app()
