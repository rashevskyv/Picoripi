"""Translation progress: the numbers, the daily history, the leaderboard of a room, and one HTML page for all of it.

Pure functions: ``summarize`` counts a snapshot of the project (the same rule as the
editor: a row needs translation when its source has text besides tags; it is done
when its current text is not empty and differs from the source); ``record_day``
keeps one entry per day in ``progress_history.json``; ``render_html`` draws the page
the app opens and the room server serves at ``/stats``.
"""
from __future__ import annotations

import datetime as _dt
import html
import json
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from core.i18n import tr
from core.tag_utils import strip_tags
from utils.atomic_io import atomic_write_json

HISTORY_NAME = "progress_history.json"
MILESTONES = (100, 500, 1000, 2500, 5000, 10000, 25000)


def _words(text: str) -> int:
    return len(strip_tags(str(text or "")).split())


def summarize(data: Sequence[Any], edited_file_data: Sequence[Any], edited_data: Mapping[tuple, str],
              block_names: Mapping[str, str], project: str = "") -> Dict[str, Any]:
    """Counts of a project snapshot: rows and source words, total and done, per block."""
    blocks, totals = [], {"rows_total": 0, "rows_done": 0, "words_total": 0, "words_done": 0}
    for block_idx, block in enumerate(data or []):
        if not isinstance(block, list):
            continue
        saved = edited_file_data[block_idx] if block_idx < len(edited_file_data or []) else None
        row = {"name": block_names.get(str(block_idx), f"#{block_idx}"), "total": 0, "done": 0, "words": 0}
        for string_idx, source in enumerate(block):
            source = str(source or "")
            if not strip_tags(source).strip():
                continue
            words = _words(source)
            row["total"] += 1
            row["words"] += words
            current = edited_data.get((block_idx, string_idx))
            if current is None and isinstance(saved, list) and string_idx < len(saved):
                current = saved[string_idx]
            if current is not None and str(current).strip() and str(current).strip() != source.strip():
                row["done"] += 1
                totals["words_done"] += words
        if row["total"]:
            blocks.append(row)
            totals["rows_total"] += row["total"]
            totals["rows_done"] += row["done"]
            totals["words_total"] += row["words"]
    return {"project": project, "generated": time.time(), **totals, "blocks": blocks}


def load_history(project_dir: Optional[Path]) -> Dict[str, Dict[str, int]]:
    path = Path(project_dir) / HISTORY_NAME if project_dir else None
    if path is None or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in data.items() if isinstance(v, dict)} if isinstance(data, dict) else {}


def record_day(project_dir: Optional[Path], summary: Mapping[str, Any], today: Optional[str] = None) -> Dict[str, Dict[str, int]]:
    """Store today's totals (one entry per day, the latest wins) and return the whole history."""
    history = load_history(project_dir)
    day = today or _dt.date.today().isoformat()
    history[day] = {"rows_done": int(summary["rows_done"]), "words_done": int(summary["words_done"])}
    if project_dir:
        try:
            atomic_write_json(Path(project_dir) / HISTORY_NAME, dict(sorted(history.items())), indent=1)
        except OSError:
            pass
    return history


def daily_gains(history: Mapping[str, Mapping[str, int]]) -> List[tuple]:
    """``[(day, rows gained that day), ...]`` in day order; the first recorded day counts from zero."""
    days = sorted(history)
    gains, previous = [], None
    for day in days:
        done = int(history[day].get("rows_done", 0))
        gains.append((day, done - previous if previous is not None else 0))
        previous = done
    return gains


def streak(history: Mapping[str, Mapping[str, int]], today: Optional[str] = None) -> int:
    """Days in a row, ending today or yesterday, on which the translated count grew."""
    gains = dict(daily_gains(history))
    day = _dt.date.fromisoformat(today) if today else _dt.date.today()
    if gains.get(day.isoformat(), 0) <= 0:
        day -= _dt.timedelta(days=1)
    count = 0
    while gains.get(day.isoformat(), 0) > 0:
        count += 1
        day -= _dt.timedelta(days=1)
    return count


def eta_days(summary: Mapping[str, Any], history: Mapping[str, Mapping[str, int]], window: int = 7) -> Optional[int]:
    """Days left at the average pace of the last ``window`` recorded days; None without a pace."""
    recent = [gain for _, gain in daily_gains(history)[-window:] if gain > 0]
    left = summary["rows_total"] - summary["rows_done"]
    if left <= 0:
        return 0
    if not recent:
        return None
    pace = sum(recent) / len(recent)
    return int(-(-left // pace))


def leaderboard(stats: Mapping[str, Mapping[str, Mapping[str, int]]], today: Optional[str] = None) -> List[Dict[str, Any]]:
    """A room's ``{name: {day: {rows, words, edits}}}`` as rows sorted by words, with today's numbers."""
    day = today or _dt.date.today().isoformat()
    board = []
    for name, days in stats.items():
        total = {"rows": 0, "words": 0, "edits": 0}
        for counts in days.values():
            for field in total:
                total[field] += int(counts.get(field, 0))
        board.append({"name": name, **total, "today_words": int(days.get(day, {}).get("words", 0)),
                      "today_rows": int(days.get(day, {}).get("rows", 0)), "days": len(days)})
    return sorted(board, key=lambda r: (-r["words"], -r["rows"], r["name"].casefold()))


def badges(summary: Mapping[str, Any], history: Mapping[str, Mapping[str, int]]) -> List[str]:
    """What the team earned: milestones of translated rows, finished blocks, a streak."""
    earned = [tr('{count} rows translated', count=f"{m:,}") for m in MILESTONES if summary["rows_done"] >= m]
    finished = sum(1 for b in summary["blocks"] if b["total"] and b["done"] >= b["total"])
    if finished:
        earned.append(tr('{count} block(s) finished', count=finished))
    days = streak(history)
    if days >= 3:
        earned.append(tr('{count}-day streak', count=days))
    return earned


# ── the page ─────────────────────────────────────────────────────────────

_CSS = """
:root{--bg:#f6f7f4;--fg:#1d2420;--muted:#5d6760;--line:#d8dcd5;--panel:#fff;--accent:#2a7a5f;--accent2:#c7862b;--track:#e3e8e2}
@media (prefers-color-scheme:dark){:root{--bg:#131715;--fg:#e6e9e4;--muted:#a1aaa3;--line:#2c332f;--panel:#1b201d;--accent:#5fc49f;--accent2:#e2a957;--track:#29302c}}
body{background:var(--bg);color:var(--fg);font:15px/1.5 "Segoe UI",system-ui,sans-serif;margin:0}
.wrap{max-width:960px;margin:0 auto;padding:24px 16px 48px}
h1{font-size:1.6rem;margin:0 0 4px}h2{font-size:1.15rem;margin:28px 0 10px}
.meta{color:var(--muted);font-size:.85rem}
.top{display:flex;flex-wrap:wrap;gap:20px;align-items:center;margin-top:16px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;flex:1;min-width:260px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:10px 12px}
.card b{display:block;font-size:1.35rem;font-variant-numeric:tabular-nums}.card span{color:var(--muted);font-size:.8rem}
table{border-collapse:collapse;width:100%;background:var(--panel);border:1px solid var(--line);border-radius:8px}
td,th{padding:6px 10px;border-bottom:1px solid var(--line);text-align:left;font-variant-numeric:tabular-nums}
th{font-size:.75rem;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}
.bar{background:var(--track);border-radius:4px;height:10px;min-width:120px}.bar i{display:block;height:10px;border-radius:4px;background:var(--accent)}
.badge{display:inline-block;background:var(--panel);border:1px solid var(--accent2);color:var(--accent2);border-radius:999px;padding:3px 10px;margin:3px;font-size:.85rem}
.medal{font-size:1.1rem}
svg text{fill:var(--muted);font-size:11px}
"""


def _ring(done: int, total: int) -> str:
    share = done / total if total else 0.0
    circumference = 2 * 3.14159 * 54
    return (
        '<svg width="150" height="150" viewBox="0 0 150 150" role="img" aria-label="progress">'
        '<circle cx="75" cy="75" r="54" fill="none" stroke="var(--track)" stroke-width="16"/>'
        f'<circle cx="75" cy="75" r="54" fill="none" stroke="var(--accent)" stroke-width="16" stroke-linecap="round" '
        f'stroke-dasharray="{circumference * share:.1f} {circumference:.1f}" transform="rotate(-90 75 75)"/>'
        f'<text x="75" y="82" text-anchor="middle" style="font-size:26px;fill:var(--fg);font-weight:600">{share:.0%}</text>'
        '</svg>'
    )


def _history_chart(history: Mapping[str, Mapping[str, int]]) -> str:
    days = sorted(history)[-60:]
    if len(days) < 2:
        return f'<p class="meta">{html.escape(tr("The chart appears after a second day of work."))}</p>'
    values = [int(history[d].get("rows_done", 0)) for d in days]
    low, high = min(values), max(values)
    span = max(1, high - low)
    width, height = 900, 160
    step = width / (len(days) - 1)
    points = " ".join(f"{i * step:.1f},{height - 20 - (v - low) / span * (height - 40):.1f}" for i, v in enumerate(values))
    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="history">'
        f'<polyline points="0,{height - 20} {points} {width},{height - 20}" fill="var(--accent)" fill-opacity=".15" stroke="none"/>'
        f'<polyline points="{points}" fill="none" stroke="var(--accent)" stroke-width="2.5"/>'
        f'<text x="0" y="{height - 4}">{html.escape(days[0])}</text>'
        f'<text x="{width}" y="{height - 4}" text-anchor="end">{html.escape(days[-1])}: {values[-1]:,}</text>'
        '</svg>'
    )


def render_html(summary: Mapping[str, Any], history: Mapping[str, Mapping[str, int]],
                board: Optional[Iterable[Mapping[str, Any]]] = None, refresh_seconds: int = 0) -> str:
    """The progress page: overall ring, numbers, team board, badges, history, blocks with the most left."""
    esc = html.escape
    done, total = summary["rows_done"], summary["rows_total"]
    eta = eta_days(summary, history)
    today_gain = dict(daily_gains(history)).get(_dt.date.today().isoformat(), 0)
    cards = [
        (f"{done:,} / {total:,}", tr('rows translated')),
        (f"{summary['words_done']:,}", tr('source words translated')),
        (f"{total - done:,}", tr('rows left')),
        (f"+{today_gain:,}", tr('rows today')),
        (f"{streak(history)}", tr('days in a row')),
        (tr('{count} days', count=eta) if eta is not None else "—", tr('to the end at this pace')),
    ]
    parts = [
        "<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>",
        f"<meta http-equiv='refresh' content='{refresh_seconds}'>" if refresh_seconds else "",
        f"<title>{esc(tr('Progress'))} · {esc(summary.get('project') or 'Picoripi')}</title><style>{_CSS}</style></head>",
        "<body><div class='wrap'>",
        f"<h1>{esc(summary.get('project') or tr('Translation progress'))}</h1>",
        f"<div class='meta'>{esc(tr('Updated {time}', time=time.strftime('%Y-%m-%d %H:%M', time.localtime(summary.get('generated') or time.time()))))}</div>",
        f"<div class='top'>{_ring(done, total)}<div class='cards'>",
        *[f"<div class='card'><b>{esc(value)}</b><span>{esc(label)}</span></div>" for value, label in cards],
        "</div></div>",
    ]
    rows = list(board or [])
    if rows:
        medals = ["🥇", "🥈", "🥉"]
        parts.append(f"<h2>{esc(tr('Team'))}</h2><table><tr><th></th><th>{esc(tr('Name'))}</th><th>{esc(tr('Words'))}</th>"
                     f"<th>{esc(tr('Rows'))}</th><th>{esc(tr('Edits'))}</th><th>{esc(tr('Today'))}</th></tr>")
        for place, person in enumerate(rows):
            medal = medals[place] if place < 3 and person["words"] else ""
            parts.append(f"<tr><td class='medal'>{medal}</td><td>{esc(person['name'])}</td><td>{person['words']:,}</td>"
                         f"<td>{person['rows']:,}</td><td>{person['edits']:,}</td><td>+{person['today_words']:,}</td></tr>")
        parts.append("</table>")
        best_today = max(rows, key=lambda r: r["today_words"])
        if best_today["today_words"]:
            words_today = f"{best_today['today_words']:,}"
            parts.append(f"<p><b>{esc(tr('Leader of the day: {name}, +{words} words.', name=best_today['name'], words=words_today))}</b></p>")
        leader = rows[0]
        if len(rows) > 1 and leader["words"]:
            gap = leader["words"] - rows[1]["words"]
            parts.append(f"<p class='meta'>{esc(tr('{second} is {gap} words behind {leader}.', second=rows[1]['name'], gap=f'{gap:,}', leader=leader['name']))}</p>")
    earned = badges(summary, history)
    if earned:
        parts.append(f"<h2>{esc(tr('Achievements'))}</h2><div>")
        parts.extend(f"<span class='badge'>★ {esc(b)}</span>" for b in earned)
        parts.append("</div>")
    parts.append(f"<h2>{esc(tr('Progress by day'))}</h2>{_history_chart(history)}")
    blocks = sorted(summary["blocks"], key=lambda b: (b["done"] >= b["total"], -(b["total"] - b["done"])))[:40]
    if blocks:
        parts.append(f"<h2>{esc(tr('Blocks with the most left'))}</h2><table><tr><th>{esc(tr('Block'))}</th>"
                     f"<th>{esc(tr('Done'))}</th><th></th></tr>")
        for block in blocks:
            share = block["done"] / block["total"] if block["total"] else 0
            parts.append(f"<tr><td>{esc(block['name'])}</td><td>{block['done']:,} / {block['total']:,}</td>"
                         f"<td><div class='bar'><i style='width:{share:.1%}'></i></div></td></tr>")
        parts.append("</table>")
    parts.append("</div></body></html>")
    return "".join(parts)
