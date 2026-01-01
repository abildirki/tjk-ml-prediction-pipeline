import csv
import io
from typing import List, Dict, Optional
from datetime import datetime, date
from ..models.race import Race, Entry, SurfaceType
from ..models.enums import Gender
from .utils import normalize_text, parse_float, parse_int

class CsvParser:
    def __init__(self):
        self.races = []
        self.current_race = None
        self.current_race_entries = []
        self.headers = {}

    def parse_csv(self, csv_content: str, date_obj: date, city: str) -> List[Race]:
        """
        Parses the TJK CSV content (Results Format) into a list of Race objects.
        """
        lines = csv_content.splitlines()
        print(f"DEBUG: CSV Lines: {len(lines)}")
        # if lines: print(f"DEBUG: First line: {lines[0]}")
        
        self.races = []
        self.current_race = None
        self.current_race_entries = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Remove BOM if present
            if line.startswith('\ufeff'):
                line = line[1:]

            parts = [p.strip() for p in line.split(';')]
            
            # Detect Race Header (e.g., "1. Kosu : 18.30;...")
            # print(f"DEBUG Check Line: {parts[0]}")
            if ("Kosu" in parts[0] or "Koşu" in parts[0]) and ":" in parts[0]:
                print(f"DEBUG: Found Race Header: {parts[0]}")
                if self.current_race and self.current_race_entries:
                    self._finalize_current_race()
                
                self._parse_race_header(line, date_obj, city)
                continue
            
            # Detect Column Headers (e.g., "At No;At İsmi;...")
            if "At No" in parts and "At İsmi" in parts:
                self.headers = {name: i for i, name in enumerate(parts)}
                continue
            
            # Parse Entry Row
            if self.current_race and len(parts) > 2 and parts[0].isdigit():
                self._parse_entry(line)

        # Finalize last race
        if self.current_race and self.current_race_entries:
            self._finalize_current_race()
            
        return self.races

    def _finalize_current_race(self):
        if self.current_race and self.current_race_entries:
            # Calculate Ranks based on time
            # Filter entries with valid times
            valid_entries = []
            no_time_entries = []
            
            for e in self.current_race_entries:
                if e.finish_time and ':' in e.finish_time:
                    valid_entries.append(e)
                else:
                    no_time_entries.append(e)
            
            # Simple Sort by time string (e.g. "1:23.45" < "1:24.00")
            valid_entries.sort(key=lambda x: x.finish_time)
            
            for i, entry in enumerate(valid_entries):
                entry.rank = i + 1
                
            self.current_race.entries = valid_entries + no_time_entries
            self.races.append(self.current_race)
            self.current_race = None
            self.current_race_entries = []

    def _parse_race_header(self, line: str, date_obj: date, city: str):
        parts = line.split(';')
        # Format: 1. Kosu : 17.45;Maiden;...
        race_no_str = parts[0].split('.')[0].strip()
        time_str = parts[0].split(':')[-1].strip()
        
        distance = 0
        surface = SurfaceType.KUM
        
        for p in parts:
            p = p.strip()
            if p.endswith('m') and p[:-1].isdigit():
                distance = int(p[:-1])
            if p in ['Kum', 'Sentetik', 'Çim']:
                if 'Çim' in p: surface = SurfaceType.CIM
                elif 'Sentetik' in p: surface = SurfaceType.SENTETIK
                else: surface = SurfaceType.KUM

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

    def _parse_entry(self, line: str):
        parts = line.split(';')
        
        def get_val(col_name):
            # Fallback indices if headers not found (Results CSV Standard)
            # At No;At İsmi;Yaş;Baba;Anne;Kilo;Jokey;Sahip;Antrenör;St;AGF;H;Derece;Ganyan;Fark
            # 0     1       2   3    4    5    6     7     8        9  10 11 12     13     14
            default_map = {
                "At No": 0, "At İsmi": 1, "Kilo": 5, "Jokey Adı": 6, 
                "Sahip Adı": 7, "Antrenör Adı": 8, "H": 11, "HP": 11,
                "Derece": 12, "Ganyan": 13, "KGS": 99, "s20": 99 # KGS/s20 might be missing in Results
            }
            
            idx = self.headers.get(col_name)
            if idx is None:
                idx = default_map.get(col_name)
            
            if idx is not None and idx < len(parts):
                return parts[idx].strip()
            return ""

        try:
            horse_name_raw = get_val("At İsmi")
            if not horse_name_raw: return

            # Extract Name and Equipment
            from .utils import extract_equipment
            cleaned_name, equipment = extract_equipment(horse_name_raw)
            cleaned_name = normalize_text(cleaned_name)
            
            if not cleaned_name: return

            entry = Entry(
                race_id=self.current_race.race_id,
                horse_id=normalize_text(cleaned_name), 
                horse_name=cleaned_name, 
                saddle_no=parse_int(get_val("At No")),
                jockey_name=normalize_text(get_val("Jokey Adı")),
                weight_kg=parse_float(get_val("Kilo")),
                owner_id=normalize_text(get_val("Sahip Adı")),
                trainer_id=normalize_text(get_val("Antrenör Adı")),
                hp=parse_int(get_val("H") or get_val("HP")),
                kgs=parse_int(get_val("KGS")), 
                s20=parse_int(get_val("s20")),
                
                finish_time=get_val("Derece"),
                ganyan=get_val("Ganyan"),
                equipment=equipment # New field
            )
            self.current_race_entries.append(entry)
        except Exception as e:
            print(f"Error parsing entry: {e}")
            pass
