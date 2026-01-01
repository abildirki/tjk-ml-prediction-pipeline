import csv
from datetime import date
from typing import List, Optional
from ..models.race import Race, Entry, SurfaceType
from ..models.horse import HorseProfile
from bs4 import BeautifulSoup
from .utils import normalize_text, parse_float, parse_int, extract_equipment

class ProgramParser:
    def parse_cities(self, html_content: str) -> List[dict]:
        soup = BeautifulSoup(html_content, 'html.parser')
        cities = []
        
        # Look for city buttons/tabs containing "Yarış Günü" or foreign country names
        # Based on previous logs: "Bursa (7. Yarış Günü)", "Kempton Park Birleşik Krallık"
        
        # 1. Standard Cities
        for tag in soup.find_all(['a', 'div', 'span', 'button']):
            text = tag.get_text(strip=True)
            if ("Yarış Günü" in text or "Y.G." in text) and len(text) < 50:
                cities.append({'name': text})
            # Foreign cities usually don't have "Yarış Günü" suffix in some views, but logging showed them.
            # They might appear in the same container.
            
        # 2. Try to find the specific container for cities if 1 yields nothing
        # But for now, let's rely on the text heuristcs that worked before (implied)
        # Actually, foreign cities in logs: 'Kempton Park Birleşik Krallık', 'Finger Lakes ABD'
        foreign_suffixes = ["ABD", "Birleşik Krallık", "Fransa", "Guney Afrika", "Avustralya", "İrlanda", "Şili", "Almanya"]
        
        for tag in soup.find_all(['a', 'div', 'span']):
            text = tag.get_text(strip=True)
            if any(s in text for s in foreign_suffixes) and len(text) < 50:
                 cities.append({'name': text})

        # Deduplicate
        seen = set()
        unique = []
        for c in cities:
            if c['name'] not in seen:
                unique.append(c)
                seen.add(c['name'])
        return unique

class ProgramCsvParser:
    def __init__(self):
        self.races = []
        self.current_race = None
        self.current_race_entries = []
        self.headers = {}
        
    def parse_csv(self, csv_content: str, date_obj: date, city: str) -> List[Race]:
        lines = csv_content.splitlines()
        self.races = []
        self.current_race = None
        self.current_race_entries = []
        
        for line in lines:
            line = line.strip()
            if not line: continue
            if line.startswith('\ufeff'): line = line[1:]
            
            parts = [p.strip() for p in line.split(';')]
            
            # Race Header
            if ("Kosu" in parts[0] or "Koşu" in parts[0]) and ":" in parts[0]:
                if self.current_race:
                    self._finalize_current_race()
                self._parse_race_header(line, date_obj, city)
                continue
                
            # Headers
            if "At No" in parts and "At İsmi" in parts:
                self.headers = {name: i for i, name in enumerate(parts)}
                continue
                
            # Entry Row
            if self.current_race and len(parts) > 2 and parts[0].isdigit():
                self._parse_entry(line)
                
        if self.current_race:
            self._finalize_current_race()
            
        return self.races

    def _parse_race_header(self, line: str, date_obj: date, city: str):
        parts = line.split(';')
        race_no_str = parts[0].split('.')[0].strip()
        
        distance = 0
        surface = SurfaceType.KUM
        
        for p in parts:
            p = p.strip()
            if p.endswith('m') and p[:-1].isdigit():
                distance = int(p[:-1])
            if p in ['Kum', 'Sentetik', 'Çim']:
                if 'Çim' in p: surface = SurfaceType.CIM
                elif 'Sentetik' in p: surface = SurfaceType.SENTETIK
                
        self.current_race = Race(
            race_id=f"{date_obj.isoformat()}_{city}_{race_no_str}",
            date=date_obj,
            city=city,
            race_no=int(race_no_str),
            dst_code=f"{distance}{surface.value[0]}",
            track_type=surface.value,
            distance_m=distance,
            surface=surface,
            entries=[]
        )
        self.current_race_entries = []

    def _finalize_current_race(self):
        if self.current_race:
            self.current_race.entries = self.current_race_entries
            self.races.append(self.current_race)
            self.current_race = None
            self.current_race_entries = []

    def _parse_entry(self, line: str):
        parts = line.split(';')
        
        def get_val(col_name):
            # Program CSV specific indices fallback
            # At No;At İsmi;Yaş;Orijin(Baba);Orijin(Anne);Kilo;Jokey Adı;Sahip Adı;Antrenör Adı;St;AGF;H;Son 6 Yarış;KGS;s20
            # 0     1       2   3            4            5    6         7         8            9  10  11 12          13  14
            default_map = {
                "At No": 0, "At İsmi": 1, "Yaş": 2, "Orijin(Baba)": 3, "Orijin(Anne)": 4,
                "Kilo": 5, "Jokey Adı": 6, "Sahip Adı": 7, "Antrenör Adı": 8, "St": 9,
                "AGF": 10, "H": 11, "HP": 11, "Son 6 Yarış": 12, "KGS": 13, "s20": 14
            }
            idx = self.headers.get(col_name)
            if idx is None: idx = default_map.get(col_name)
            
            if idx is not None and idx < len(parts):
                return parts[idx].strip()
            return ""

        try:
            raw_name = get_val("At İsmi")
            if not raw_name: return
            
            clean_name, equipment = extract_equipment(raw_name)
            clean_name = normalize_text(clean_name)
            
            if not clean_name: return
            
            # AGF Parsing: "%28.33(1)" -> 28.33
            agf_raw = get_val("AGF")
            agf_val = 0.0
            if '%' in agf_raw:
                try:
                    agf_val = float(agf_raw.split('%')[1].split('(')[0])
                except: pass
                
            entry = Entry(
                race_id=self.current_race.race_id,
                horse_id=normalize_text(clean_name),
                horse_name=clean_name,
                saddle_no=parse_int(get_val("At No")),
                jockey_name=normalize_text(get_val("Jokey Adı")),
                weight_kg=parse_float(get_val("Kilo")),
                owner_id=normalize_text(get_val("Sahip Adı")),
                trainer_id=normalize_text(get_val("Antrenör Adı")),
                hp=parse_int(get_val("H") or get_val("HP")),
                kgs=parse_int(get_val("KGS")),
                s20=parse_int(get_val("s20")),
                agf=agf_val,
                form_score=get_val("Son 6 Yarış"),
                equipment=equipment,
                # Rank/Time unknown yet
            )
            
            # Additional metadata for saving to Horse Table separate call?
            # Ideally we pass this info to repo or attach to Entry and let Repo handle it
            # For now, we trust Repo to handle 'sire' and 'dam' if we modify Entry to hold it temporarily?
            # Or we can return a tuple (Entry, HorseProfile) ?
            # Let's keep it simple: Entry has fields, Repo extracts them. 
            # But Entry model doesn't have sire/dam.
            # I added them to HORSE model.
            
            # Let's attach them to entry as extra attributes (not fields) or add to EntryModel?
            # No, 'sire' and 'dam' are static horse info.
            
            self.current_race_entries.append(entry)
            
            # We need to pass the Pedigree info out somehow.
            # I will inject it into entry as a temporary attribute '_temp_horse_info'
            entry._temp_horse_info = {
                'sire': get_val("Orijin(Baba)"),
                'dam': get_val("Orijin(Anne)"),
                'age_text': get_val("Yaş")
            }
            
        except Exception as e:
            print(f"Error parsing program entry: {e}")
