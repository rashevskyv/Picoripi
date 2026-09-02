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

fuki_kind selects the screen class in dMsgObject_c::talkStartInit
(d_msg_object.cpp). Line counts come from getLineMax (non-JP). Preview
geometry falls back to HIO-scaled layout; when a local retail dump is
present, `window_frame_loader` paints BLO/BTI frames from res/Layout.

The BFN preview only turns this chrome on when the active plugin advertises
the ``message_window_preview`` capability (see GameRules.get_capabilities).
"""
from typing import Any, Dict, List, Optional, Union

# fuki_kind -> screen (dusklight dMsgObject_c::talkStartInit):
#   9        dMsgScrnItem_c
#   2        dMsgScrnTree_c     (wooden sign)
#   6        dMsgScrnKanban_c   (stone sign)
#   7        dMsgScrnStaff_c
#   12       dMsgScrnPlace_c
#   19       dMsgScrnBoss_c
#   17       dMsgScrnHowl_c
#   1, 5     dMsgScrnJimaku_c
#   10       sets a flag, then falls through to Talk
#   default  dMsgScrnTalk_c — includes 0,3,4,8,10,11,13,14,15,16,18
#            (8 = light-spirit text layout; 11 = pause-menu item description
#            with Talk chrome, NOT dMsgScrnItem_c; 15 = Talk visuals + kanban
#            pagination via isKanbanMessage {2,6,15})
#   message_id 0x02A5 always uses Item even when kind would fall through
# dMsgScrnExplain_c is NOT selected by BMG fuki_kind (manual preview only).

# Special message that forces the Item screen regardless of fuki_kind.
ITEM_FORCE_MESSAGE_ID = 0x02A5

# Manual-only preview key (not a real fuki_kind).
EXPLAIN_PRESET_KEY = "explain"

# GameCube NTSC framebuffer used as the preview "screen" reference.
_SCREEN = (608, 448)

_TALK_FRAME = {
    "style": "talk",
    "fill": "#000000",
    "fill_alpha": 140,
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


# Non-JP mg_e4lin TBX2 (fontSize / lineSpace / charSpace).
_METRICS_TALK = {"font_x": 23.0, "font_y": 22.0, "line_space": 23.0, "char_space": 1.0}
_METRICS_ITEM = {"font_x": 23.0, "font_y": 23.0, "line_space": 23.0, "char_space": 1.0}
_METRICS_SIGN = {"font_x": 25.0, "font_y": 23.0, "line_space": 23.0, "char_space": 1.0}


def _geometry(text_xywh, hio_xy=(1.0, 1.0), text_pane_widen=1.0,
              pad_xy=(22.0, 10.0), metrics=None):
    """Stable screen-space box + inner text for preview (not exact BLO pixels).

    text_xywh is the unscaled text pane; HIO scale and optional 1.2x text-pane
    widen from the screen constructors are baked into the returned rects so
    paint code can scale them uniformly to the preview viewport.
    """
    tx, ty, tw, th = text_xywh
    hx, hy = hio_xy
    tw = tw * text_pane_widen * hx
    th = th * hy
    # Keep the pane roughly centered horizontally after widening/scaling.
    tx = tx - (tw - text_xywh[2]) / 2.0
    ty = ty - (th - text_xywh[3]) * 0.15
    pad_x, pad_y = pad_xy[0] * hx, pad_xy[1] * hy
    out = {
        "screen": list(_SCREEN),
        "text": [tx, ty, tw, th],
        "box": [tx - pad_x, ty - pad_y, tw + 2 * pad_x, th + 2 * pad_y],
        "hio_scale": [hx, hy],
    }
    if metrics:
        out["text_metrics"] = dict(metrics)
    return out


# Approximate base text panes before HIO / pane widen (font-pixel layout).
_GEOM_TALK = _geometry((76, 292, 410, 118), hio_xy=(1.2, 1.0),
                       text_pane_widen=1.2, pad_xy=(22.0, 10.0),
                       metrics=_METRICS_TALK)
_GEOM_ITEM = _geometry((70, 280, 360, 130), hio_xy=(1.05, 0.97),
                       text_pane_widen=1.2, pad_xy=(22.0, 12.0),
                       metrics=_METRICS_ITEM)
_GEOM_WOOD = _geometry((120, 70, 360, 260), hio_xy=(1.0, 1.0),
                       text_pane_widen=1.2, pad_xy=(26.0, 14.0),
                       metrics=_METRICS_SIGN)
_GEOM_STONE = _geometry((120, 70, 360, 260), hio_xy=(1.0, 1.0),
                        text_pane_widen=1.2, pad_xy=(26.0, 14.0),
                        metrics=_METRICS_SIGN)
_GEOM_HOWL = _geometry((150, 180, 300, 140), hio_xy=(1.05, 1.1),
                       text_pane_widen=1.0, pad_xy=(16.0, 10.0))
_GEOM_PLACE = _geometry((94, 200, 420, 48), hio_xy=(1.0, 1.0),
                        text_pane_widen=1.0, pad_xy=(30.0, 6.0))
_GEOM_JIMAKU = _geometry((74, 380, 460, 50), hio_xy=(1.0, 1.0),
                         text_pane_widen=1.2, pad_xy=(12.0, 4.0))
_GEOM_BOSS = _geometry((94, 190, 420, 56), hio_xy=(1.0, 1.0),
                       text_pane_widen=1.0, pad_xy=(20.0, 8.0))
_GEOM_STAFF = _geometry((80, 40, 448, 360), hio_xy=(1.0, 1.0),
                        text_pane_widen=1.0, pad_xy=(16.0, 12.0))
_GEOM_EXPLAIN = _geometry((90, 120, 420, 200), hio_xy=(1.2, 1.0),
                          text_pane_widen=1.2, pad_xy=(22.0, 12.0),
                          metrics=_METRICS_TALK)


def _style(kind_name, frame, halo=_HALO_TALK, shadow=_TALK_SHADOW,
           default_text_color=None, item_icon=None, text_offset=(4.5, 0.0),
           geometry=None, screen_class="talk"):
    style: Dict[str, Any] = {
        "kind_name": kind_name,
        "frame": frame,
        "text_offset": text_offset,
        "text_brightness": 200.0 / 255.0,
        "screen_class": screen_class,
        # Talk/item are dark; kanban signs are light. COutFont bullet is TEV
        # black — correct on wood/stone, invisible on dialogue unless inverted.
        "bullet_tint": "#e6dcc8" if screen_class in ("talk", "item", "explain", "jimaku") else "#000000",
    }
    if halo:
        style["halo"] = dict(halo)
    if shadow:
        style["shadow"] = dict(shadow)
    if default_text_color:
        style["default_text_color"] = default_text_color
    if item_icon:
        style["item_icon"] = dict(item_icon)
    if geometry:
        style["geometry"] = dict(geometry)
        if isinstance(geometry.get("text"), list):
            style["geometry"]["text"] = list(geometry["text"])
        if isinstance(geometry.get("box"), list):
            style["geometry"]["box"] = list(geometry["box"])
        if isinstance(geometry.get("screen"), list):
            style["geometry"]["screen"] = list(geometry["screen"])
    return style


def _talk(kind_name="Dialogue", geometry=_GEOM_TALK, **kw):
    return _style(kind_name, dict(_TALK_FRAME), geometry=geometry,
                  screen_class="talk", **kw)


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
    "fill": "#000000",
    "fill_alpha": 77,
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

_EXPLAIN_FRAME = {
    "style": "explain",
    "fill": "#101418",
    "fill_alpha": 230,
    "border": "#d2c8a0",
    "border_alpha": 70,
    "radius": 12.0,
    "pad_x": 22.0,
    "pad_y": 12.0,
}

# fuki_kind -> preview style
WINDOW_KIND_STYLES: Dict[int, Dict[str, Any]] = {
    # cutscene subtitles: bare text over the scene, no window
    1: _style("Subtitles", None, halo=None, geometry=_GEOM_JIMAKU,
              screen_class="jimaku"),
    5: _style("Subtitles", None, halo=None, geometry=_GEOM_JIMAKU,
              screen_class="jimaku"),
    # wooden / stone signs
    2: _style("Wooden sign", _WOOD_FRAME, halo=None, geometry=_GEOM_WOOD,
              screen_class="tree"),
    6: _style("Stone sign", _STONE_FRAME, halo=None, geometry=_GEOM_STONE,
              screen_class="kanban"),
    # staff credits
    7: _style("Staff credits", None, halo=None, geometry=_GEOM_STAFF,
              screen_class="staff"),
    # light spirit window (Talk + spirit text layout / halo type 2)
    8: _talk("Light spirit", halo=_HALO_SPIRIT),
    # item get / item explanation window: item icon on the left,
    # text starts to the right of it
    9: _style("Item get", _ITEM_FRAME, halo=None,
              item_icon={"size": 48.0, "gap": 10.0}, geometry=_GEOM_ITEM,
              screen_class="item"),
    # Pause-menu / collection description. talkStartInit falls through to
    # Talk (not Item). item_no in INF1 names the collectible; no get-window icon.
    11: _talk("Item info"),
    # location name plate
    12: _style("Location name", _PLATE_FRAME, halo=None, geometry=_GEOM_PLACE,
              screen_class="place"),
    # Midna's window: cyan default text, blue halo
    13: _talk("Midna", halo=_HALO_MIDNA, default_text_color="#82e6e6"),
    # green-text talk variant (getFontCCColorTable fukiKind 14)
    14: _talk("Dialogue (green)", halo=_HALO_GREEN,
              default_text_color="#96dc64"),
    # Talk visuals + kanban pagination (isKanbanMessage), NOT a wooden sign
    15: _talk("Dialogue (kanban)"),
    # descriptions / save window (Talk class, getLineMax 6)
    16: _talk("Descriptions / save"),
    # howling stone: bare text
    17: _style("Howling stone", None, halo=None, geometry=_GEOM_HOWL,
              screen_class="howl"),
    # boss name: bare centered caption
    19: _style("Boss name", None, halo=None, geometry=_GEOM_BOSS,
              screen_class="boss"),
}

# Manual preview preset only — never selected from INF1 fuki_kind.
EXPLAIN_WINDOW_STYLE = _style(
    "Explain", _EXPLAIN_FRAME, halo=_HALO_TALK, geometry=_GEOM_EXPLAIN,
    screen_class="explain",
)

_DEFAULT_TALK = _talk()

# Non-JP getLineMax fallbacks used when window_layouts.json has no override.
# isKanbanMessage kinds 2/6/15 -> 7; staff 7 -> 10; save 16 -> 6; else 4.
DEFAULT_LINES_PER_PAGE: Dict[int, int] = {
    2: 7,
    6: 7,
    7: 10,
    15: 7,
    16: 6,
}

# Preview-only cycle order: Auto, then supported screen presets, then Explain.
# Values are fuki_kind ints, None (Auto), or EXPLAIN_PRESET_KEY.
PREVIEW_WINDOW_PRESETS: List[Optional[Union[int, str]]] = [
    None,
    0,   # Dialogue (Talk)
    2,   # Wooden sign
    6,   # Stone sign
    9,   # Item get
    11,  # Item info (Talk)
    7,   # Staff
    12,  # Place
    19,  # Boss
    17,  # Howl
    1,   # Subtitles
    8,   # Light spirit
    13,  # Midna
    14,  # Dialogue (green)
    15,  # Dialogue (kanban)
    16,  # Descriptions / save
    EXPLAIN_PRESET_KEY,
]


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
        "item_no": u8(8),
        "se_mood": u8(10),
        "camera_id": u8(11),
        "base_anm_id": u8(12),
        "face_anm_id": u8(13),
    }


def effective_fuki_kind(attrs: Optional[Dict[str, int]]) -> Optional[int]:
    """fuki_kind used for preview/layout, including the 0x02A5 Item force."""
    if not attrs:
        return None
    if int(attrs.get("message_id") or 0) == ITEM_FORCE_MESSAGE_ID:
        return 9
    kind = attrs.get("fuki_kind")
    return int(kind) if kind is not None else None


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
    kind = int(fuki_kind or 0)
    merged: Dict[str, Any] = {}
    for source in (layouts.get("default") or {},
                   (layouts.get("kinds") or {}).get(kind, {})):
        for key, value in source.items():
            if value is None or value == "":
                continue
            merged[key] = value
    # Fill getLineMax when JSON has no explicit lines_per_page for the kind.
    if "lines_per_page" not in merged or not isinstance(merged.get("lines_per_page"), int):
        if kind in DEFAULT_LINES_PER_PAGE:
            merged["lines_per_page"] = DEFAULT_LINES_PER_PAGE[kind]
    return merged


def _copy_style(style: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(style)
    if isinstance(out.get("frame"), dict):
        out["frame"] = dict(out["frame"])
    if isinstance(out.get("geometry"), dict):
        geom = dict(out["geometry"])
        for key in ("screen", "text", "box", "hio_scale"):
            if isinstance(geom.get(key), list):
                geom[key] = list(geom[key])
        if isinstance(geom.get("text_metrics"), dict):
            geom["text_metrics"] = dict(geom["text_metrics"])
        out["geometry"] = geom
    if isinstance(out.get("item_icon"), dict):
        out["item_icon"] = dict(out["item_icon"])
    if isinstance(out.get("halo"), dict):
        out["halo"] = dict(out["halo"])
    if isinstance(out.get("shadow"), dict):
        out["shadow"] = dict(out["shadow"])
    return out


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
    out = _copy_style(style)
    out["fuki_kind"] = kind

    custom_name = (layout or {}).get("name")
    if isinstance(custom_name, str) and custom_name:
        out["kind_name"] = custom_name
    elif not known and kind != 0:
        out["kind_name"] = f"Dialogue (kind {kind})"

    lines = (layout or {}).get("lines_per_page")
    if isinstance(lines, int) and lines > 0:
        out["lines_per_page"] = lines
    elif kind in DEFAULT_LINES_PER_PAGE:
        out["lines_per_page"] = DEFAULT_LINES_PER_PAGE[kind]
    return out


def window_style_for_preset(preset: Optional[Union[int, str]],
                            layout: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Style for a preview override preset (Auto is resolved by the caller)."""
    if preset == EXPLAIN_PRESET_KEY:
        out = _copy_style(EXPLAIN_WINDOW_STYLE)
        out["fuki_kind"] = None
        out["preset_key"] = EXPLAIN_PRESET_KEY
        lines = (layout or {}).get("lines_per_page")
        out["lines_per_page"] = lines if isinstance(lines, int) and lines > 0 else 6
        return out
    return window_style_for_kind(int(preset) if preset is not None else 0, layout)


def preset_label(preset: Optional[Union[int, str]],
                 auto_style: Optional[Dict[str, Any]] = None) -> str:
    """Compact label for the preview override control."""
    if preset is None:
        name = (auto_style or {}).get("kind_name") or "Dialogue"
        return f"Auto: {name}"
    if preset == EXPLAIN_PRESET_KEY:
        return "Explain"
    return window_style_for_kind(int(preset)).get("kind_name", str(preset))
