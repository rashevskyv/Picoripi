import os
import re
from typing import Dict, List, Any, Optional


def _clean_heading_title(text: str) -> str:
    title = re.sub(r"^\s*\d+(?:\.\d+)*\.?\s*", "", text or "").strip()
    return title.strip(":-–— ").strip()


def _clean_action_text(text: str) -> str:
    action = (text or "").strip()
    italic = re.fullmatch(r"(?:\*(?P<star>.*?)\*|_(?P<under>.*?)_)", action)
    if italic:
        action = (italic.group("star") or italic.group("under") or "").strip()
    return action


def _is_glossary_root_title(title: str) -> bool:
    lowered = _clean_heading_title(title).casefold()
    return lowered in {
        "glossary",
        "script glossary",
        "glossary context",
        "mempalace glossary",
    }


def _is_character_category(title: str) -> bool:
    lowered = _clean_heading_title(title).casefold()
    hints = ("character", "characters", "speaker", "speakers", "cast", "npc", "npcs", "people")
    return any(hint in lowered for hint in hints)


def _clean_inline_value(text: str) -> str:
    return (text or "").strip().strip("`").strip()


def parse_markdown_script(file_path: str) -> Dict[str, Any]:
    """
    Parse a standardized Markdown game script file into structured data.
    Extracts global synopsis, characters cast with attributes, terms, 
    and chronological chapters with locations, actions, and dialogues.
    """
    data = {
        "synopsis": "",
        "characters": [],
        "terms": [],
        "dialogues": [],
        "chapters": []
    }

    if not file_path or not os.path.exists(file_path):
        return data

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception:
        try:
            with open(file_path, "r", encoding="cp1252", errors="replace") as f:
                lines = f.readlines()
        except Exception:
            return data

    # State tracking
    current_section = "NONE"
    synopsis_paragraphs = []
    in_glossary = False
    glossary_root_level: Optional[int] = None
    current_glossary_category: Optional[str] = None
    
    # Character parsing states
    current_char = None
    # Term parsing states
    current_term = None
    
    # Timeline tracking states
    current_chapter = None
    current_location = "Generic_Location"
    current_action = ""
    
    # Regexes for parsing
    heading_regex = re.compile(r'^(?P<marks>#{1,6})\s+(?P<title>.+?)\s*$')
    char_header_regex = re.compile(
        r'^\s{0,1}[\-\*]\s*\*\*(?P<id>[^*]+?)\*\*'
        r'(?:\s*\((?:Name in Game:\s*)?`?(?P<display>[^`\)]+)`?\))?'
        r'(?:\s*[:\-]\s*(?P<desc>.*))?\s*$',
        re.IGNORECASE,
    )
    term_header_regex = re.compile(
        r'^\s{0,1}[\-\*]\s*\*\*(?P<id>[^*]+?)\*\*'
        r'(?:\s*\((?:Original:\s*)?`?(?P<orig>[^`\)]+)`?\))?'
        r'(?:\s*[:\-]\s*(?P<desc>.*))?\s*$',
        re.IGNORECASE,
    )
    inline_entry_regex = re.compile(
        r'^\s*(?:[\-\*]\s*)?(?:\*\*(?P<bold>[^*]+?)\*\*|(?P<plain>[^:]+?))\s*:\s*(?P<desc>.+?)\s*$'
    )
    
    sub_bullet_regex = re.compile(r'^\s+[\-\*]\s*\*\*(?P<key>[a-zA-Z0-9_\s]+)\*\*:\s*`?(?P<val>.*?)`?$', re.IGNORECASE)
    
    chapter_regex = re.compile(r'^(?:#{1,6})\s+(Chapter\s+[^:\-–—]+|Act\s+[^:\-–—]+|Prologue|Epilogue)\s*[:\-–—]?\s*(.*)', re.IGNORECASE)
    location_regex = re.compile(r'^###\s*Location:\s*(.*)', re.IGNORECASE)
    action_regex = re.compile(
        r'^(?:\{(?:Action|Context):\s*(?P<braced>.*)\}|\[(?P<bracketed>.*)\])$',
        re.IGNORECASE,
    )
    dialogue_regex = re.compile(r'^(?:\*\*(?P<bold>[^*]+)\*\*|(?P<plain>[A-Z0-9_\s\-#]{2,})):\s*(?P<text>.*)$')

    def flush_glossary_entry():
        nonlocal current_char, current_term
        if current_char:
            data["characters"].append(current_char)
            current_char = None
        if current_term:
            data["terms"].append(current_term)
            current_term = None

    def new_character(name: str, display_name: str, description: str = "") -> Dict[str, Any]:
        return {
            "name": name,
            "display_name": display_name,
            "translation": display_name,
            "gender": "unknown",
            "age_group": "unknown",
            "relationship_summary": "",
            "address_type": "",
            "description": description,
            "section": current_glossary_category or "Characters",
        }

    def new_term(name: str, original: str, description: str = "") -> Dict[str, Any]:
        return {
            "name": name,
            "original": original,
            "translation": original,
            "description": description,
            "section": current_glossary_category or "Terms",
        }

    for idx, raw_line in enumerate(lines):
        line_num = idx + 1
        line = raw_line.strip()
        if not line:
            continue

        # Section detection based on headers
        heading_match = heading_regex.match(line)
        if heading_match:
            heading_level = len(heading_match.group("marks"))
            heading_title = _clean_heading_title(heading_match.group("title"))

            if in_glossary and glossary_root_level is not None and heading_level > glossary_root_level:
                flush_glossary_entry()
                current_glossary_category = heading_title or "Terms"
                current_section = "CHARACTERS" if _is_character_category(heading_title) else "TERMS"
                continue

            if in_glossary and glossary_root_level is not None and heading_level <= glossary_root_level:
                flush_glossary_entry()
                in_glossary = False
                glossary_root_level = None
                current_glossary_category = None

            # Check for section transitions
            lower_line = line.lower()
            if "synopsis" in lower_line or "plot" in lower_line:
                flush_glossary_entry()
                current_section = "SYNOPSIS"
                continue
            elif _is_glossary_root_title(heading_title):
                flush_glossary_entry()
                current_section = "GLOSSARY"
                in_glossary = True
                glossary_root_level = heading_level
                current_glossary_category = None
                continue
            elif "character" in lower_line or "cast" in lower_line:
                # Save previous if any
                flush_glossary_entry()
                current_glossary_category = "Characters"
                current_section = "CHARACTERS"
                continue
            elif "term" in lower_line or "glossary" in lower_line:
                flush_glossary_entry()
                current_glossary_category = "Terms"
                current_section = "TERMS"
                continue
            elif chapter_regex.match(line):
                flush_glossary_entry()
                current_glossary_category = None
                current_section = "TIMELINE"
                # Do not 'continue' so TIMELINE section can process the chapter match below

        # Process lines depending on active section
        if current_section == "SYNOPSIS":
            # Just collect text blocks
            if not line.startswith("#"):
                synopsis_paragraphs.append(line)

        elif current_section == "CHARACTERS":
            # Detect character item
            char_match = char_header_regex.match(raw_line)
            if char_match:
                if current_char:
                    data["characters"].append(current_char)
                char_id = _clean_inline_value(char_match.group("id"))
                disp = char_match.group("display")
                disp_name = _clean_inline_value(disp) if disp else char_id
                desc = _clean_inline_value(char_match.group("desc") or "")
                current_char = new_character(char_id, disp_name, desc)
            elif current_char:
                # Detect sub-bullet properties
                sub_match = sub_bullet_regex.match(raw_line)
                if sub_match:
                    key = sub_match.group("key").lower().replace(" ", "_")
                    val = sub_match.group("val").strip()
                    if key == "translation":
                        current_char["translation"] = val
                    elif key == "gender":
                        current_char["gender"] = val.lower()
                    elif key in ("age", "age_group"):
                        current_char["age_group"] = val.lower()
                    elif key in ("address_style", "address_type"):
                        current_char["address_type"] = val
                    elif key in ("relationship", "relations"):
                        current_char["relationship_summary"] = val
                    elif key in ("description", "notes"):
                        current_char["description"] = val
            else:
                inline_match = inline_entry_regex.match(raw_line)
                if inline_match:
                    name = _clean_inline_value(inline_match.group("bold") or inline_match.group("plain"))
                    desc = _clean_inline_value(inline_match.group("desc"))
                    if name and desc:
                        data["characters"].append(new_character(name, name, desc))

        elif current_section == "TERMS":
            # Detect term item
            term_match = term_header_regex.match(raw_line)
            if term_match:
                if current_term:
                    data["terms"].append(current_term)
                term_id = _clean_inline_value(term_match.group("id"))
                orig = term_match.group("orig")
                orig_name = _clean_inline_value(orig) if orig else term_id
                desc = _clean_inline_value(term_match.group("desc") or "")
                current_term = new_term(term_id, orig_name, desc)
            elif current_term:
                sub_match = sub_bullet_regex.match(raw_line)
                if sub_match:
                    key = sub_match.group("key").lower()
                    val = sub_match.group("val").strip()
                    if key == "translation":
                        current_term["translation"] = val
                    elif key in ("description", "notes", "definition"):
                        current_term["description"] = val
            else:
                inline_match = inline_entry_regex.match(raw_line)
                if inline_match:
                    name = _clean_inline_value(inline_match.group("bold") or inline_match.group("plain"))
                    desc = _clean_inline_value(inline_match.group("desc"))
                    if name and desc:
                        data["terms"].append(new_term(name, name, desc))

        elif current_section == "TIMELINE":
            # Detect Chapter header
            ch_match = chapter_regex.match(line)
            if ch_match:
                # Wrap up previous chapter
                if current_chapter:
                    current_chapter["end_line"] = line_num - 1
                    # Fill content
                    start_idx = current_chapter["start_line"] - 1
                    end_idx = current_chapter["end_line"]
                    current_chapter["content"] = "".join(lines[start_idx:end_idx])
                    data["chapters"].append(current_chapter)

                num = ch_match.group(1).strip()
                title = ch_match.group(2).strip()
                current_chapter = {
                    "num": num,
                    "title": title or num,
                    "start_line": line_num,
                    "end_line": len(lines),
                    "ai_summary": "",
                    "content": ""
                }
                current_action = ""
                continue

            # Detect Location
            loc_match = location_regex.match(line)
            if loc_match:
                current_location = loc_match.group(1).strip()
                continue

            # Detect Action
            act_match = action_regex.match(line)
            if act_match:
                current_action = _clean_action_text(
                    act_match.group("braced") or act_match.group("bracketed") or ""
                )
                continue

            # Detect Dialogue line
            dia_match = dialogue_regex.match(line)
            if dia_match:
                speaker = (dia_match.group("bold") or dia_match.group("plain") or "").strip()
                text = dia_match.group("text").strip()
                
                # Check for standard Markdown links or other false positives
                # If speaker has spaces/punctuation that are not in character names, check
                # But standard speaker IDs are upper-case alphabetic with optional digits/underscores.
                
                context_note = f"Action: {current_action}" if current_action else ""
                
                data["dialogues"].append({
                    "text": text,
                    "speaker": speaker,
                    "timestamp": context_note or f"Line_{line_num}",
                    "room": current_chapter["title"] if current_chapter else current_location
                })

    # Wrap up final items
    if current_char:
        data["characters"].append(current_char)
    if current_term:
        data["terms"].append(current_term)
    if current_chapter:
        current_chapter["end_line"] = len(lines)
        start_idx = current_chapter["start_line"] - 1
        current_chapter["content"] = "".join(lines[start_idx:])
        data["chapters"].append(current_chapter)

    data["synopsis"] = "\n".join(synopsis_paragraphs).strip()
    return data
