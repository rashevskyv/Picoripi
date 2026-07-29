import re
from typing import List, Dict, Any
from utils.logging_utils import log_error

def clean_chapter_title(raw_title: str) -> str:
    """Clean up spaced-out letters in chapter titles.
    e.g. 'S u b s e r v i e n t  T w i l i g h t' -> 'Subservient Twilight'
    """
    raw_title = raw_title.strip()
    # Remove standard visual separator artifacts if any
    raw_title = re.sub(r'^[–—\-?]\s*', '', raw_title)
    
    if "  " in raw_title:
        # Double spaces separate words, single spaces separate characters
        cleaned = raw_title.replace("  ", "_DBL_").replace(" ", "").replace("_DBL_", " ")
    else:
        # Check if single spaces separate characters
        words = raw_title.split()
        if len(words) > 3 and all(len(w) == 1 for w in words[:3]):
            cleaned = "".join(words)
        else:
            cleaned = raw_title
            
    # Remove trailing/leading spaces or double spacing
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

def segment_script_file(script_path: str) -> List[Dict[str, Any]]:
    """Segment the text script into structured chapters."""
    lines = []
    try:
        with open(script_path, "r", encoding="cp1252", errors="replace") as f:
            lines = f.readlines()
    except Exception as e:
        log_error(f"Failed to read script with cp1252, trying utf-8: {e}")
        try:
            with open(script_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception as e2:
            log_error(f"Failed to read script: {e2}")
            return []

    chapters = []
    # Match: Chapter I - Title or Chapter II ? Title
    chapter_regex = re.compile(r"^\s*Chapter\s+([IVXLCDM]+)\s*[\-–—?]?\s*(.*)", re.IGNORECASE)
    act_regex = re.compile(r"^\s*Act\s+([A-Za-z]+)\s*$", re.IGNORECASE)
    act_mapping = {
        "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
        "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10"
    }
    
    current_act = None
    current_chapter = None
    
    for idx, line in enumerate(lines):
        line_num = idx + 1
        
        # Check for Act marker (e.g. "Act One")
        act_match = act_regex.match(line)
        if act_match:
            act_word = act_match.group(1).lower()
            current_act = act_mapping.get(act_word, act_match.group(1))
            continue
            
        match = chapter_regex.match(line)
        if match:
            # Complete the previous chapter
            if current_chapter:
                current_chapter["end_line"] = line_num - 1
                # Grab content lines
                start_idx = current_chapter["start_line"] - 1
                end_idx = current_chapter["end_line"]
                current_chapter["content"] = "".join(lines[start_idx:end_idx])
                chapters.append(current_chapter)
                
            num = match.group(1).strip()
            raw_title = match.group(2).strip()
            title = clean_chapter_title(raw_title)
            
            display_num = f"Act {current_act}, Ch {num}" if current_act else f"Ch {num}"
            
            current_chapter = {
                "num": display_num,
                "title": title,
                "start_line": line_num,
                "end_line": len(lines),
                "ai_summary": "",
                "content": ""
            }
            
    if current_chapter:
        start_idx = current_chapter["start_line"] - 1
        current_chapter["content"] = "".join(lines[start_idx:])
        chapters.append(current_chapter)
        
    return chapters
