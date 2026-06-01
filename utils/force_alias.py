"""Force-alias utilities for AI translation.

A 'Force alias' is a tag alias whose display name starts with ``F:`` or ``f:``.
When text is prepared for AI translation:

1. Original escape tags (e.g. ``{escape:0:0000}``) are first replaced by their
   aliases using the project's ``default_tag_mappings``.
2. Force aliases (e.g. ``{F:Link}``) are then replaced with the plain word
   after the prefix (``Link``), so the AI sees a readable word it can inflect.
3. All remaining tags are stripped normally.
4. After AI returns the translation, the translated form of the word (obtained
   from the glossary) is located in the translated text and replaced back with
   the original escape tag.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

# Pattern to detect Force aliases: {F:Word} or {f:Word}
_FORCE_ALIAS_RE = re.compile(r'\{[Ff]:([^}]+)\}')


@dataclass(frozen=True)
class ForceAliasMapping:
    """One resolved Force-alias entry."""
    word: str           # The plain word extracted from the alias, e.g. "Link"
    original_tag: str   # The real game tag, e.g. "{escape:0:0000}"
    alias: str          # The Force alias itself, e.g. "{F:Link}"


def apply_aliases_to_text(text: str, tag_mappings: Dict[str, str]) -> str:
    """Replace original tags with their aliases in *text*.

    ``tag_mappings`` maps ``{alias} -> {original_tag}``.
    We apply replacements longest-original-tag first to avoid partial
    substitutions.
    """
    if not text or not tag_mappings:
        return text or ""
    sorted_mappings = sorted(tag_mappings.items(), key=lambda item: len(item[1]), reverse=True)
    result = text
    for alias, original_tag in sorted_mappings:
        if original_tag:
            result = result.replace(original_tag, alias)
    return result


def extract_force_aliases(
    text_with_aliases: str,
    tag_mappings: Dict[str, str],
) -> Tuple[str, List[ForceAliasMapping]]:
    """Find Force aliases in *text_with_aliases* and replace them with plain words.

    Returns ``(cleaned_text, mappings)`` where *cleaned_text* has Force alias
    tags replaced by their word values, and *mappings* records the association
    between each word and its original game tag.

    Parameters
    ----------
    text_with_aliases:
        Text with aliases already applied (via :func:`apply_aliases_to_text`).
    tag_mappings:
        The project's ``default_tag_mappings`` dict (``{alias: original_tag}``).
    """
    mappings: List[ForceAliasMapping] = []
    if not text_with_aliases:
        return "", mappings

    # Build a lookup from alias -> original_tag
    # (tag_mappings is already alias -> original_tag)

    def _replace(match: re.Match) -> str:
        full_alias = match.group(0)          # e.g. "{F:Link}"
        word = match.group(1)                # e.g. "Link"
        original_tag = tag_mappings.get(full_alias, "")
        mappings.append(ForceAliasMapping(
            word=word,
            original_tag=original_tag,
            alias=full_alias,
        ))
        return word

    cleaned = _FORCE_ALIAS_RE.sub(_replace, text_with_aliases)
    return cleaned, mappings


def prepare_text_for_ai(
    original_text: str,
    tag_mappings: Dict[str, str],
) -> Tuple[str, List[ForceAliasMapping]]:
    """Full pipeline: apply aliases, then extract Force aliases into plain words.

    Returns ``(text_with_force_words, force_mappings)``.
    The returned text still contains non-force tags (they are NOT stripped here;
    tag stripping is the responsibility of the caller or downstream logic).
    """
    aliased = apply_aliases_to_text(original_text, tag_mappings)
    return extract_force_aliases(aliased, tag_mappings)


def restore_force_aliases_in_translation(
    translated_text: str,
    force_mappings: List[ForceAliasMapping],
    glossary_translations: Dict[str, str],
) -> str:
    """Replace translated Force-alias words back with the original game tags.

    For each Force-alias mapping we look up all known translations of the word
    in ``glossary_translations`` (semicolon-separated) plus the original English
    word itself.  We search for these forms in *translated_text* and replace
    the **first** occurrence with the original game tag.

    Parameters
    ----------
    translated_text:
        The text returned by the AI (in target language).
    force_mappings:
        The list produced by :func:`extract_force_aliases`.
    glossary_translations:
        A dict mapping each Force-alias word (case-insensitive key) to the
        semicolon-separated translation string from the glossary.
        E.g. ``{"link": "Лінк; Лінку; Лінкові; Лінком"}``.
    """
    if not translated_text or not force_mappings:
        return translated_text or ""

    result = translated_text
    for mapping in force_mappings:
        word = mapping.word
        original_tag = mapping.original_tag

        # Collect all forms to search for: glossary translations + original word
        forms: List[str] = []
        translation_str = glossary_translations.get(word.lower(), "")
        if translation_str:
            forms.extend(v.strip() for v in translation_str.split(";") if v.strip())
        # Always include the original English word as fallback
        forms.append(word)

        # Sort forms by length descending to match longest first
        forms.sort(key=len, reverse=True)

        replaced = False
        for form in forms:
            if not form:
                continue
            # Build a word-boundary-aware pattern (works for both Latin and Cyrillic)
            escaped = re.escape(form)
            pattern = re.compile(
                r'(?<![а-яА-ЯіїІЇЄєґҐa-zA-Z0-9])'
                + escaped
                + r'(?![а-яА-ЯіїІЇЄєґҐa-zA-Z0-9])',
                re.IGNORECASE,
            )
            match = pattern.search(result)
            if match:
                result = result[:match.start()] + original_tag + result[match.end():]
                replaced = True
                break

        if not replaced:
            # Desperate fallback: simple case-insensitive search without boundaries
            for form in forms:
                if not form:
                    continue
                idx = result.lower().find(form.lower())
                if idx != -1:
                    result = result[:idx] + original_tag + result[idx + len(form):]
                    break

    return result
