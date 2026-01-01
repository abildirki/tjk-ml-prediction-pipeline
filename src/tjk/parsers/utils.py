import re
from typing import Optional

def normalize_text(text: Optional[str]) -> str:
    if not text:
        return ""
    # Remove extra whitespace and newlines
    return " ".join(text.split())

def parse_int(text: str) -> Optional[int]:
    if not text:
        return None
    try:
        # Remove non-digit chars
        clean = re.sub(r'[^\d]', '', text)
        return int(clean) if clean else None
    except:
        return None

def parse_float(text: str) -> Optional[float]:
    if not text:
        return None
    try:
        # Replace comma with dot
        clean = text.replace(',', '.')
        # Remove non-numeric chars except dot
        clean = re.sub(r'[^\d\.]', '', clean)
        # Handle multiple dots (take first valid part) - e.g. 54.50.30 -> 54.50
        if clean.count('.') > 1:
            # simple heuristic: keep only first dot? Or try to convert.
            # If 54.50.30, maybe valid is 54.5? Or just fail?
            # Let's try to just floats
            pass
        return float(clean) if clean else None
    except:
        return None

def extract_equipment(text: Optional[str]) -> tuple[str, str]:
    """
    Extracts equipment info from horse name.
    Returns: (clean_name, equipment_string)
    Example:
        "BOLD PILOT KG DB" -> ("BOLD PILOT", "KG DB")
    """
    if not text:
        return "", ""
        
    text = text.strip()
    
    # 1. Remove (Koşmaz) and similar
    text = re.sub(r'\(.*?\)', '', text).strip()
    
    suffixes = [
        'SGKR', 'GKR', 'SKG', 'DB', 'SK', 'KG', 'K', 'YP', 'ÖG', 'BB',
        'TGK', 'OG', 'DS', 'TS', 'KR'
    ]
    
    parts = text.split()
    if not parts:
        return "", ""
        
    # Iterate backwards to find suffix chain
    suffix_start_idx = len(parts)
    
    for i in range(len(parts) - 1, -1, -1):
        word = parts[i].replace('İ', 'I').upper()
        if word in suffixes:
            suffix_start_idx = i
        else:
            # If we hit a non-suffix word, stop, assuming suffixes are always at end and contiguous
            break
            
    name_parts = parts[:suffix_start_idx]
    equip_parts = parts[suffix_start_idx:]
    
    return " ".join(name_parts), " ".join(equip_parts)

def clean_horse_name(text: Optional[str]) -> str:
    # Wrapper for backward compatibility if needed, though we should switch usages
    name, _ = extract_equipment(text)
    return name
