"""TP message window kinds, decoded from the per-message INF1 attributes.

Every BMG message entry carries attribute bytes (dusklight d_msg_class.h,
JMSMesgEntry_c). In our editor `msg.info` holds the entry bytes from +0x04:

    info[0:2]  message_id      (u16)
    info[2:4]  event_label_id  (u16)
    info[4]    se_speaker      (voice/SE speaker id)
    info[5]    fuki_kind       <- WINDOW TYPE (this module)
    info[6]    output_type
    info[7]    fuki_pos_type   (window position on screen)
    info[10]   se_mood         (voice emotion)
    info[11]   camera_id
    info[12]   base_anm_id     (NPC body animation)
    info[13]   face_anm_id     (NPC face animation)

fuki_kind selects the screen class in dMsgObject (d_msg_object.cpp, the
switch creating dMsgScrn*): talk box, wooden/stone signs, item-get window,
subtitles, location plate, boss name, howling, staff credits. Talk-box
sub-kinds change the default text color and the per-character halo
(getFontCCColorTable / dMsgScrnLight color types).
"""
from typing import Any, Dict, Optional

# fuki_kind -> screen (dusklight d_msg_object.cpp, switch(mFukiKind)):
#   9        dMsgScrnItem_c    zelda_item_get_window.blo
#   2, 15    dMsgScrnTree_c    zelda_kanban_wood_a.blo   (wooden sign)
#   6        dMsgScrnKanban_c  zelda_kanban_stone_a.blo  (stone sign)
#   7        dMsgScrnStaff_c   staff credits
#   12       dMsgScrnPlace_c   location name plate
#   19       dMsgScrnBoss_c    boss name
#   17       dMsgScrnHowl_c    howling stone duet
#   1, 5     dMsgScrnJimaku_c  cutscene subtitles
#   default  dMsgScrnTalk_c    talk box (8 = light spirit window,
#            13 = Midna window, 14 = green-text variant)

_TALK_FRAME = {
    "style": "talk",
    "fill": "#0a0c14",
    "fill_alpha": 216,
    "border": "#f0e6c8",
    "border_alpha": 40,
    "radius": 14.0,
    "pad_x": 22.0,
    "pad_y": 10.0,
}

_TALK_SHADOW = {"color": "#000000", "alpha": 255, "dx": 2.0, "dy": 2.0}

# dMsgScrnLight color types (d_msg_scrn_light.cpp): 0 talk golden,
# 1 Midna blue, 2 spirit bright yellow, 4 green
_HALO_TALK = {"color": "#e1d26e", "alpha": 160, "radius_ratio": 0.9}
_HALO_MIDNA = {"color": "#286eb4", "alpha": 120, "radius_ratio": 0.9}
_HALO_SPIRIT = {"color": "#ffff6e", "alpha": 210, "radius_ratio": 0.9}
_HALO_GREEN = {"color": "#469600", "alpha": 150, "radius_ratio": 0.9}


def _style(kind_name, frame, halo=_HALO_TALK, shadow=_TALK_SHADOW,
           default_text_color=None, item_icon=None, text_offset=(4.5, 0.0)):
    style: Dict[str, Any] = {
        "kind_name": kind_name,
        "frame": frame,
        "text_offset": text_offset,
        "text_brightness": 200.0 / 255.0,
    }
    if halo:
        style["halo"] = dict(halo)
    if shadow:
        style["shadow"] = dict(shadow)
    if default_text_color:
        style["default_text_color"] = default_text_color
    if item_icon:
        style["item_icon"] = dict(item_icon)
    return style


def _talk(kind_name="Dialogue", **kw):
    return _style(kind_name, dict(_TALK_FRAME), **kw)


_WOOD_FRAME = {
    "style": "wood",
    "fill": "#6b4a2b",
    "fill2": "#4a3018",
    "fill_alpha": 245,
    "border": "#2e1d0c",
    "border_alpha": 255,
    "radius": 10.0,
    "pad_x": 26.0,
    "pad_y": 14.0,
}

_STONE_FRAME = {
    "style": "stone",
    "fill": "#8a8a88",
    "fill2": "#5f5f5c",
    "fill_alpha": 245,
    "border": "#3c3c38",
    "border_alpha": 255,
    "radius": 8.0,
    "pad_x": 26.0,
    "pad_y": 14.0,
}

_ITEM_FRAME = {
    "style": "item",
    "fill": "#101a30",
    "fill_alpha": 222,
    "border": "#f0e6c8",
    "border_alpha": 60,
    "radius": 14.0,
    "pad_x": 22.0,
    "pad_y": 12.0,
}

_PLATE_FRAME = {
    "style": "plate",
    "fill": "#000000",
    "fill_alpha": 150,
    "border": "#ffffff",
    "border_alpha": 25,
    "radius": 6.0,
    "pad_x": 30.0,
    "pad_y": 6.0,
}

# fuki_kind -> preview style
WINDOW_KIND_STYLES: Dict[int, Dict[str, Any]] = {
    # cutscene subtitles: bare text over the scene, no window
    1: _style("Subtitles", None, halo=None),
    5: _style("Subtitles", None, halo=None),
    # signs
    2: _style("Wooden sign", _WOOD_FRAME, halo=None),
    15: _style("Wooden sign", _WOOD_FRAME, halo=None),
    6: _style("Stone sign", _STONE_FRAME, halo=None),
    # staff credits
    7: _style("Staff credits", None, halo=None),
    # light spirit window
    8: _talk("Light spirit", halo=_HALO_SPIRIT),
    # item get / item explanation window: item icon on the left,
    # text starts to the right of it
    9: _style("Item get", _ITEM_FRAME, halo=None,
              item_icon={"size": 48.0, "gap": 10.0}),
    # location name plate
    12: _style("Location name", _PLATE_FRAME, halo=None),
    # Midna's window: cyan default text, blue halo
    13: _talk("Midna", halo=_HALO_MIDNA, default_text_color="#82e6e6"),
    # green-text talk variant (getFontCCColorTable fukiKind 14)
    14: _talk("Dialogue (green)", halo=_HALO_GREEN, default_text_color="#96dc64"),
    # save/continue window (dMsgObject isSaveMessage)
    16: _talk("Save window"),
    # howling stone: bare text
    17: _style("Howling stone", None, halo=None),
    # boss name: bare centered caption
    19: _style("Boss name", None, halo=None),
}

_DEFAULT_TALK = _talk()


def decode_message_attributes(info: Optional[bytes]) -> Dict[str, int]:
    """Decode the BMG INF1 attribute bytes (msg.info) into named fields."""
    data = bytes(info or b"")

    def u8(off):
        return data[off] if len(data) > off else 0

    def u16(off):
        return (data[off] << 8) | data[off + 1] if len(data) > off + 1 else 0

    return {
        "message_id": u16(0),
        "event_label_id": u16(2),
        "se_speaker": u8(4),
        "fuki_kind": u8(5),
        "output_type": u8(6),
        "fuki_pos_type": u8(7),
        "se_mood": u8(10),
        "camera_id": u8(11),
        "base_anm_id": u8(12),
        "face_anm_id": u8(13),
    }


def window_kind_name(fuki_kind: int) -> str:
    style = WINDOW_KIND_STYLES.get(fuki_kind)
    if style:
        return style["kind_name"]
    return "Dialogue"


def load_window_layouts(plugin_dir: Optional[str] = None) -> Dict[str, Any]:
    """Load window_layouts.json: per-fuki_kind width limits, font and
    lines-per-page. Returns {"default": {...}, "kinds": {int: {...}}}."""
    import json
    import os
    if plugin_dir is None:
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(plugin_dir, "window_layouts.json")
    result = {"default": {}, "kinds": {}}
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        if isinstance(doc.get("default"), dict):
            result["default"] = doc["default"]
        for key, entry in (doc.get("kinds") or {}).items():
            if not isinstance(entry, dict):
                continue
            try:
                result["kinds"][int(key, 0)] = entry
            except (TypeError, ValueError):
                continue
    except Exception:
        pass
    return result


def layout_for_kind(layouts: Dict[str, Any], fuki_kind: Optional[int]) -> Dict[str, Any]:
    """Merged layout for a window kind: default entry overlaid with the
    kind-specific one; None/empty values are dropped."""
    merged: Dict[str, Any] = {}
    for source in (layouts.get("default") or {},
                   (layouts.get("kinds") or {}).get(int(fuki_kind or 0), {})):
        for key, value in source.items():
            if value is None or value == "":
                continue
            merged[key] = value
    return merged


def window_style_for_kind(fuki_kind: Optional[int],
                          layout: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Preview style for a fuki_kind; unknown/None -> normal talk box.

    layout (from window_layouts.json) may override "name" — this lets users
    classify window kinds that the catalog doesn't know yet — and provides
    lines_per_page for pagination.
    """
    kind = int(fuki_kind) if fuki_kind is not None else 0
    style = WINDOW_KIND_STYLES.get(kind)
    known = style is not None
    if style is None:
        style = _DEFAULT_TALK
    # shallow copy so callers can annotate without mutating the catalog
    out = dict(style)
    if isinstance(out.get("frame"), dict):
        out["frame"] = dict(out["frame"])
    out["fuki_kind"] = kind

    custom_name = (layout or {}).get("name")
    if isinstance(custom_name, str) and custom_name:
        out["kind_name"] = custom_name
    elif not known and kind != 0:
        # surface the raw kind so unknown window types can be identified
        # and then described in window_layouts.json
        out["kind_name"] = f"Dialogue (kind {kind})"

    lines = (layout or {}).get("lines_per_page")
    if isinstance(lines, int) and lines > 0:
        out["lines_per_page"] = lines
    return out
