from selectolax.parser import HTMLParser
from typing import Optional
from ..models.race import Race, Entry, SurfaceType
from .utils import normalize_text, parse_int, parse_float

class RaceParser:
    def parse_race_detail(self, html: str, race_stub: dict) -> Race:
        """Parses the detailed race information."""
        tree = HTMLParser(html)
        
        # Parse conditions
        # TODO: Inspect live HTML for specific selectors
        conditions_text = normalize_text(tree.css_first('.race-config').text()) if tree.css_first('.race-config') else ""
        
        distance = 0
        surface = SurfaceType.UNKNOWN
        
        # Simple heuristic for distance and surface
        if "Kum" in conditions_text:
            surface = SurfaceType.KUM
        elif "Çim" in conditions_text:
            surface = SurfaceType.CIM
            
        # Extract distance (e.g. "1400")
        # This needs a robust regex in a real implementation
        
        entries = self._parse_entries(tree, race_stub['race_id'])
        
        return Race(
            race_id=race_stub['race_id'],
            date=race_stub['date'],
            city=race_stub['city'],
            race_no=race_stub['race_no'],
            distance_m=distance, # Placeholder
            surface=surface,
            entries=entries
        )

    def _parse_entries(self, tree: HTMLParser, race_id: str) -> list[Entry]:
        entries = []
        # Find the main table
        with open("debug_race.html", "w", encoding="utf-8") as f:
            f.write(tree.html)
            
        table = tree.css_first('table.tablesorter')
        if not table:
            print("DEBUG: Table 'table.tablesorter' NOT found in HTML.")
            # print(f"DEBUG: HTML snippet: {tree.html[:500]}")
            return []
            
        print(f"DEBUG: Table found with {len(table.css('tbody tr'))} rows.")
            
        for row in table.css('tbody tr'):
            cells = row.css('td')
            if len(cells) < 5:
                continue
                
            # Extract data based on column index (needs mapping logic like in v1 but cleaner)
            # Placeholder implementation
            try:
                saddle_no = parse_int(cells[1].text())
                horse_name = normalize_text(cells[2].text())
                jockey_name = normalize_text(cells[6].text())
                weight = parse_float(cells[5].text())
                
                entries.append(Entry(
                    race_id=race_id,
                    horse_id=horse_name, # Temporary ID
                    horse_name=horse_name,
                    saddle_no=saddle_no,
                    jockey_name=jockey_name,
                    weight_kg=weight
                ))
            except Exception:
                continue
                
        return entries
