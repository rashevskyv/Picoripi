"""Window styles, presets and glyph text preparation for the Yo-kai Watch preview."""
from typing import Optional, Dict, Any, List, Tuple
from plugins.yokai_watch import tags


def get_preview_window_style(rules: Any, block_idx: Optional[int] = None, string_idx: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Approximate message window style for in-app translation preview.

    Note: These window styles are approximate viewport layout guides for previewing line breaks and fitting,
    not exact extracted BLO widget frames. YW4 and Academy Y do not provide preview layouts.
    """
    game = rules._game()
    if game in ("yw4", "yay"):
        return None

    cat = "dialogue"
    if block_idx is not None and string_idx is not None:
        found = rules._row(block_idx, string_idx)
        if found:
            rel, row, root = found
            from .rules import category
            cat = category(rel, row.kind, row.param)
            game = rules._game(root)
    from .rules import _ROLES
    role = _ROLES.get(cat, ("Text", ""))[0]
    lines = 2 if cat == "dialogue" else (1 if cat in ("name", "plural", "battle", "menu") else 4)

    if game == "ywnx":
        # Switch (1280x720): native ft_nrm.xf font_y=51, line_space=62.
        # 2 lines: 51 + 62 = 113px <= 190px text area.
        # 4 lines: 51 + 3 * 62 = 237px <= 290px text area.
        # 1 line: 51px <= 80px text area.
        if cat == "dialogue":
            geom = {
                "screen": [1280, 720],
                "box": [50, 420, 1180, 260],
                "text": [90, 460, 1100, 190],
                "text_metrics": {"font_y": 51, "line_space": 62, "char_space": 0},
            }
        elif lines == 4:
            geom = {
                "screen": [1280, 720],
                "box": [50, 330, 1180, 350],
                "text": [90, 360, 1100, 290],
                "text_metrics": {"font_y": 51, "line_space": 62, "char_space": 0},
            }
        else:
            geom = {
                "screen": [1280, 720],
                "box": [50, 520, 1180, 140],
                "text": [90, 555, 1100, 80],
                "text_metrics": {"font_y": 51, "line_space": 62, "char_space": 0},
            }
    else:
        # 3DS (400x240): native ft_nrm.xf font_y=18, line_space=22.
        # 2 lines: 18 + 22 = 40px <= 62px text area.
        # 4 lines: 18 + 3 * 22 = 84px <= 94px text area.
        # 1 line: 18px <= 26px text area.
        if cat == "dialogue":
            geom = {
                "screen": [400, 240],
                "box": [16, 140, 368, 86],
                "text": [28, 152, 344, 62],
                "text_metrics": {"font_y": 18, "line_space": 22, "char_space": 0},
            }
        elif lines == 4:
            geom = {
                "screen": [400, 240],
                "box": [16, 110, 368, 116],
                "text": [28, 122, 344, 94],
                "text_metrics": {"font_y": 18, "line_space": 22, "char_space": 0},
            }
        else:
            geom = {
                "screen": [400, 240],
                "box": [16, 170, 368, 48],
                "text": [28, 182, 344, 26],
                "text_metrics": {"font_y": 18, "line_space": 22, "char_space": 0},
            }

    return {
        "kind": cat,
        "kind_name": role,
        "lines_per_page": lines,
        "geometry": geom,
        "default_text_color": "#ffffff",
    }


def get_window_presets(rules: Any) -> list:
    if rules._game() in ("yw4", "yay"):
        return []
    return [None, "dialogue", "system"]


def get_window_preset_label(rules: Any, preset: Any, auto_style: Any = None) -> str:
    if preset is None:
        kind_name = auto_style.get("kind_name") if isinstance(auto_style, dict) else None
        return f"Auto: {kind_name}" if kind_name else "Auto"
    from .rules import _ROLES
    return _ROLES.get(preset, (str(preset).title(), ""))[0]


def get_window_style_for_preset(rules: Any, preset: Any) -> Optional[Dict[str, Any]]:
    """Window style for explicit preset selection (approximate layout guide)."""
    game = rules._game()
    if game in ("yw4", "yay"):
        return None
    if preset in ("dialogue", "system", None):
        cat = preset or "dialogue"
        from .rules import _ROLES
        role = _ROLES.get(cat, ("Dialogue", ""))[0]
        lines = 4 if cat == "system" else 2
        if game == "ywnx":
            if cat == "system":
                geom = {
                    "screen": [1280, 720],
                    "box": [50, 330, 1180, 350],
                    "text": [90, 360, 1100, 290],
                    "text_metrics": {"font_y": 51, "line_space": 62, "char_space": 0},
                }
            else:
                geom = {
                    "screen": [1280, 720],
                    "box": [50, 420, 1180, 260],
                    "text": [90, 460, 1100, 190],
                    "text_metrics": {"font_y": 51, "line_space": 62, "char_space": 0},
                }
        else:
            if cat == "system":
                geom = {
                    "screen": [400, 240],
                    "box": [16, 110, 368, 116],
                    "text": [28, 122, 344, 94],
                    "text_metrics": {"font_y": 18, "line_space": 22, "char_space": 0},
                }
            else:
                geom = {
                    "screen": [400, 240],
                    "box": [16, 140, 368, 86],
                    "text": [28, 152, 344, 62],
                    "text_metrics": {"font_y": 18, "line_space": 22, "char_space": 0},
                }
        return {
            "kind": cat,
            "kind_name": role,
            "lines_per_page": lines,
            "geometry": geom,
            "default_text_color": "#ffffff",
        }
    return None


def prepare_preview_glyph_text(rules: Any, text: str) -> Tuple[str, List[Optional[str]], List[float], Any]:
    """Clean tags and prepare glyph text, colors and page breaks for the preview."""
    body = str(text or "")
    lines_per_page = 2
    hero_name = "Nate"
    try:
        mw = getattr(rules, "mw", None)
        if mw and hasattr(mw, "data_store"):
            ds = mw.data_store
            b_idx = getattr(ds, "physical_block_idx", None)
            s_idx = getattr(ds, "current_string_idx", None)
            if b_idx is not None and s_idx is not None:
                layout = rules.get_string_layout(b_idx, s_idx)
                if layout and layout.get("lines_per_page"):
                    lines_per_page = int(layout["lines_per_page"])
                found = rules._row(b_idx, s_idx)
                if found:
                    rel, _row, _root = found
                    rel_norm = rel.replace("\\", "/").lower()
                    if "_f_" in rel_norm or rel_norm.endswith(("_f.cfg.bin", "_f.bin")):
                        hero_name = "Katie"
    except (AttributeError, TypeError, ValueError):
        pass

    out: List[str] = []
    color_of: List[Optional[str]] = []
    scale_of: List[float] = []
    color: Optional[str] = None
    scale = 1.0

    def put(chars: str) -> None:
        for char in chars:
            out.append(char)
            color_of.append(color)
            scale_of.append(scale)

    position = 0
    for match in list(tags.TAG_RE.finditer(body)) + [None]:
        put(body[position:match.start() if match else len(body)])
        if match is None:
            break
        tag = match.group(0)
        if tag.startswith("{") and tag.endswith("}"):
            tag_content = tag[1:-1]
            if tag_content == "PAGE":
                used = "".join(out).count("\n") + 1
                put("\n" * (lines_per_page - (used - 1) % lines_per_page))
            elif tag_content in ("/C", "/CR"):
                color = None
            elif tag_content == "CR":
                color = "#ff4444"
            elif tag_content == "CG":
                color = "#44cc44"
            elif tag_content == "CY":
                color = "#ffcc00"
            elif tag_content == "CN":
                color = "#44bbee"
            elif tag_content.startswith('C"') and tag_content.endswith('"'):
                hex_code = tag_content[2:-1]
                color = f"#{hex_code}" if len(hex_code) in (3, 6, 8) else None
            elif tag_content in ("PNAMEF", "PNAME02") or tag_content.endswith("_F"):
                put("Katie")
            elif tag_content in ("PNAMEM", "PNAME01") or tag_content.endswith("_M"):
                put("Nate")
            elif tag_content.startswith("PNAME"):
                put(hero_name)
            elif tag_content == "CHARA_NAME":
                put("Yo-kai")
            elif tag_content == "ITEM_NAME":
                put("Item")
        elif tag.startswith("[") and tag.endswith("]"):
            if tag in ("[C]", "[/C]"):
                color = None
            elif tag.startswith("[CR"):
                color = "#ff4444"
            elif tag.startswith("[CG"):
                color = "#44cc44"
            elif tag.startswith("[CY"):
                color = "#ffcc00"
        position = match.end()

    clean = "".join(out)
    return clean, color_of, scale_of, None
