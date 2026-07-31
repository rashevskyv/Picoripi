"""Zelda Wiki lookup: this game's external source of lore.

Lives in the plugin because it is true of Zelda and of nothing else. The engine
asks a plugin for lore about a term through ``get_external_lore`` and has no
idea a wiki is involved; a plugin for another game answers from its own source,
or not at all.

Returns English prose exactly as published. Translating it is the caller's job:
the plugin knows where the lore is, the engine owns the AI provider and the
target language.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from typing import Optional

from utils.logging_utils import log_info, log_warning


_API = "https://zelda.fandom.com/api.php"
_USER_AGENT = "Picoripi Localization Tool/1.0 (Contact: admin@picoripi.org)"
_TIMEOUT = 5
_MAX_WIKITEXT = 1500

# Disambiguates terms that exist across the series -- "Zelda" alone lands on a
# page spanning every game.
_GAME_QUALIFIER = "Twilight Princess"


def _get_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


def _query(**params) -> str:
    params.setdefault("format", "json")
    return f"{_API}?" + "&".join(
        f"{key}={urllib.parse.quote(str(value))}" for key, value in params.items()
    )


def _clean_wikitext(raw: str) -> str:
    """Strip templates, files and links down to readable prose."""
    text = raw
    # Templates nest; five passes clears the depths that occur in practice.
    for _ in range(5):
        text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    text = re.sub(r"\[\[(File|Category|Image):[^\]]+\]\]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\[\[[^\]|]+\|([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = text.strip()
    if len(text) > _MAX_WIKITEXT:
        text = text[:_MAX_WIKITEXT] + "..."
    return text


def _find_title(term: str) -> Optional[str]:
    data = _get_json(_query(action="query", list="search",
                            srsearch=f"{term} {_GAME_QUALIFIER}"))
    results = data.get("query", {}).get("search", [])
    return results[0].get("title") if results else None


def _intro_extract(title: str) -> str:
    data = _get_json(_query(action="query", prop="extracts", exintro=1,
                            explaintext=1, titles=title, redirects=1))
    for page in (data.get("query", {}).get("pages", {}) or {}).values():
        extract = (page.get("extract") or "").strip()
        if extract:
            return extract
    return ""


def _raw_wikitext(title: str) -> str:
    """Fallback for pages whose intro is entirely templates and infoboxes."""
    data = _get_json(_query(action="query", prop="revisions", rvprop="content",
                            rvslots="main", titles=title, redirects=1))
    for page in (data.get("query", {}).get("pages", {}) or {}).values():
        revisions = page.get("revisions") or []
        if not revisions:
            continue
        slot = (revisions[0].get("slots") or {}).get("main") or {}
        raw = slot.get("*") or slot.get("content") or ""
        if raw:
            return _clean_wikitext(raw)
    return ""


def lookup(term: str) -> Optional[str]:
    """English lore about ``term``, or None when the wiki has nothing usable.

    Never raises: a wiki that is unreachable, rate limited or has simply never
    heard of the term is a missing nicety, not a failure of the caller's work.
    """
    if not term or not term.strip():
        return None
    try:
        title = _find_title(term.strip())
        if not title:
            return None

        extract = _intro_extract(title)
        if extract:
            log_info(f"Zelda Wiki: found an extract for '{term}' (page: {title})")
            return f"Page: {title}\n{extract}"

        log_info(f"Zelda Wiki: extract empty for '{term}', trying raw wikitext")
        wikitext = _raw_wikitext(title)
        if wikitext:
            log_info(f"Zelda Wiki: found raw wikitext for '{term}' (page: {title})")
            return f"Page: {title}\n{wikitext}"
    except Exception as exc:
        log_warning(f"Zelda Wiki lookup failed for '{term}': {exc}")
    return None
