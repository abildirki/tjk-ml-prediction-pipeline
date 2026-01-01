from selectolax.parser import HTMLParser
from ..models.horse import HorseProfile, PastPerformance

class HorseParser:
    def parse_profile(self, html: str, horse_id: str) -> HorseProfile:
        tree = HTMLParser(html)
        
        name = normalize_text(tree.css_first('h1').text()) if tree.css_first('h1') else "Unknown"
        
        return HorseProfile(
            horse_id=horse_id,
            name=name
        )
